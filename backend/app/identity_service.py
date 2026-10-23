"""Transactional identity policies shared by HTTP routes and local bootstrap."""

import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.identity_security import AuthError, Passwords, digest, token, valid_token


def utcnow():
    return datetime.now(UTC)


def lock(connection):
    connection.execute(text("SELECT id FROM namespace_lock WHERE id=1 FOR UPDATE"))


def public_user(row):
    return {key: row[key] for key in ("id", "email", "role", "active", "theme")}


class Identity:
    def __init__(self, engine, settings, clock=utcnow):
        self.engine, self.settings, self.clock = engine, settings, clock
        self.passwords = Passwords()

    def audit(self, connection, actor, action, target, request_id):
        connection.execute(
            text("""INSERT INTO activity
            (id,actor_id,action,target_id,target_name,request_id)
            VALUES (:id,:actor,:action,:target,'Account security',:request)"""),
            {
                "id": uuid.uuid4(),
                "actor": actor,
                "action": action,
                "target": target,
                "request": request_id,
            },
        )

    def limit(self, peer: str, purpose: str, email: str | None = None):
        now = self.clock()
        rules = [(f"{purpose}:peer:{peer}", 30)]
        if email is not None:
            rules.append((f"{purpose}:email:{email.casefold()}", 10))
        exceeded = False
        with self.engine.begin() as connection:
            # Serialize bounded bucket allocation independently of identity transactions.
            connection.execute(text("SELECT pg_advisory_xact_lock(735103)"))
            connection.execute(
                text("DELETE FROM auth_rate_limits WHERE expires_at<=:now"), {"now": now}
            )
            for key, budget in rules:
                hashed = hmac.digest(
                    self.settings.auth_rate_secret.get_secret_value().encode(),
                    key.encode(),
                    hashlib.sha256,
                )
                if connection.scalar(text("SELECT count(*) FROM auth_rate_limits")) >= 4096:
                    exceeded = True
                    break
                attempts = connection.scalar(
                    text("""INSERT INTO auth_rate_limits
                    (key_hash,attempts,expires_at) VALUES (:key,1,:expires)
                    ON CONFLICT (key_hash) DO UPDATE SET
                    attempts=LEAST(auth_rate_limits.attempts+1,1001)
                    RETURNING attempts"""),
                    {"key": hashed, "expires": now + timedelta(minutes=15)},
                )
                exceeded = exceeded or attempts > budget
        if exceeded:
            raise AuthError(429, "rate_limited", "Too many attempts. Try again later")

    def actor(self, connection, session_token, csrf=None, *, mutation=False, admin=False):
        if not valid_token(session_token):
            raise AuthError(401, "authentication_required", "Please sign in")
        now = self.clock()
        row = (
            connection.execute(
                text("""SELECT u.id,u.email,u.role,u.active,u.theme,
            s.id AS session_id,s.csrf_hash,s.absolute_expires_at,s.idle_expires_at
            FROM sessions s JOIN users u ON u.id=s.user_id
            WHERE s.token_hash=:hash AND s.revoked_at IS NULL AND u.active
            AND s.idle_expires_at>:now AND s.absolute_expires_at>:now"""),
                {"hash": digest(session_token), "now": now},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise AuthError(401, "authentication_required", "Please sign in again")
        if mutation and (
            not valid_token(csrf) or not hmac.compare_digest(digest(csrf), bytes(row["csrf_hash"]))
        ):
            raise AuthError(403, "csrf_failed", "Refresh the page and try again")
        if admin and row["role"] != "admin":
            raise AuthError(403, "administrator_required", "Administrator access required")
        connection.execute(
            text("""UPDATE sessions SET last_seen_at=:now,
            idle_expires_at=:idle WHERE id=:id AND revoked_at IS NULL"""),
            {
                "now": now,
                "idle": min(now + timedelta(hours=24), row["absolute_expires_at"]),
                "id": row["session_id"],
            },
        )
        return row

    def new_session(self, connection, user, old_token):
        now = self.clock()
        if valid_token(old_token):
            connection.execute(
                text("UPDATE sessions SET revoked_at=:now WHERE token_hash=:hash"),
                {"now": now, "hash": digest(old_token)},
            )
        session_token, csrf = token(), token()
        connection.execute(
            text("""INSERT INTO sessions (id,user_id,token_hash,csrf_hash,
            created_at,last_seen_at,idle_expires_at,absolute_expires_at)
            VALUES (:id,:user,:hash,:csrf,:now,:now,:idle,:absolute)"""),
            {
                "id": uuid.uuid4(),
                "user": user["id"],
                "hash": digest(session_token),
                "csrf": digest(csrf),
                "now": now,
                "idle": now + timedelta(hours=24),
                "absolute": now + timedelta(days=7),
            },
        )
        return {"user": public_user(user)}, session_token, csrf

    def bootstrap(self, email, password):
        with self.engine.begin() as connection:
            lock(connection)
            if connection.scalar(text("SELECT count(*) FROM users")):
                raise AuthError(
                    409, "already_initialized", "Bootstrap requires an empty user table"
                )
            user = self.insert_user(connection, email, password, "admin")
            self.audit(connection, user["id"], "bootstrap", user["id"], uuid.uuid4())
            return public_user(user)

    def insert_user(self, connection, email, password, role="member"):
        if connection.scalar(text("SELECT count(*) FROM users")) >= 5:
            raise AuthError(409, "registration_full", "This cloud has reached its account limit")
        if connection.scalar(
            text("SELECT 1 FROM users WHERE email_key=:key"), {"key": email.casefold()}
        ):
            raise AuthError(
                409, "account_unavailable", "Unable to create an account with these details"
            )
        hashed = self.passwords.hash(password)
        return (
            connection.execute(
                text("""INSERT INTO users
            (id,email,email_key,password_hash,role) VALUES (:id,:email,:key,:hash,:role)
            RETURNING id,email,role,active,theme"""),
                {
                    "id": uuid.uuid4(),
                    "email": email,
                    "key": email.casefold(),
                    "hash": hashed,
                    "role": role,
                },
            )
            .mappings()
            .one()
        )

    def login(self, data, old_token, peer, request_id):
        self.limit(peer, "login", str(data.email))
        with self.engine.begin() as connection:
            lock(connection)
            row = (
                connection.execute(
                    text("SELECT * FROM users WHERE email_key=:key"),
                    {"key": str(data.email).casefold()},
                )
                .mappings()
                .first()
            )
            valid = self.passwords.verify(
                row["password_hash"] if row else None, data.password.get_secret_value()
            )
            if not valid or not row["active"]:
                raise AuthError(401, "invalid_credentials", "Email or password is incorrect")
            if self.passwords.hasher.check_needs_rehash(row["password_hash"]):
                connection.execute(
                    text("UPDATE users SET password_hash=:hash WHERE id=:id"),
                    {
                        "id": row["id"],
                        "hash": self.passwords.hash(data.password.get_secret_value()),
                    },
                )
            result = self.new_session(connection, row, old_token)
            self.audit(connection, row["id"], "login", row["id"], request_id)
            return result

    def redeem(self, data, old_token, peer, request_id):
        self.limit(peer, "redeem")
        with self.engine.begin() as connection:
            lock(connection)
            invitation = (
                connection.execute(
                    text("""SELECT id FROM invitations
                WHERE token_hash=:hash AND redeemed_at IS NULL AND revoked_at IS NULL
                AND expires_at>:now"""),
                    {"hash": digest(data.token.get_secret_value()), "now": self.clock()},
                )
                .mappings()
                .first()
            )
            if invitation is None:
                raise AuthError(400, "invitation_unavailable", "This invitation is unavailable")
            user = self.insert_user(connection, str(data.email), data.password.get_secret_value())
            connection.execute(
                text("""UPDATE invitations SET redeemed_at=:now,redeemed_by=:user
                WHERE id=:id"""),
                {"now": self.clock(), "user": user["id"], "id": invitation["id"]},
            )
            self.audit(connection, user["id"], "user_register", user["id"], request_id)
            return self.new_session(connection, user, old_token)

    def me(self, session_token):
        with self.engine.begin() as connection:
            actor = self.actor(connection, session_token)
            return {
                "user": public_user(actor),
                "csrf_cookie": self.settings.csrf_cookie,
                "expires_at": min(self.clock() + timedelta(hours=24), actor["absolute_expires_at"]),
            }

    def logout(self, session_token, csrf, request_id):
        with self.engine.begin() as connection:
            lock(connection)
            actor = self.actor(connection, session_token, csrf, mutation=True)
            connection.execute(
                text("UPDATE sessions SET revoked_at=:now WHERE id=:id"),
                {"now": self.clock(), "id": actor["session_id"]},
            )
            self.audit(connection, actor["id"], "logout", actor["id"], request_id)

    def invitations(self, session_token):
        with self.engine.begin() as connection:
            self.actor(connection, session_token, admin=True)
            return [
                dict(row)
                for row in connection.execute(
                    text("""SELECT id,created_at,
                expires_at,redeemed_at,revoked_at FROM invitations
                ORDER BY created_at DESC,id DESC LIMIT 100""")
                ).mappings()
            ]

    def create_invitation(self, session_token, csrf, request_id):
        with self.engine.begin() as connection:
            lock(connection)
            actor = self.actor(connection, session_token, csrf, mutation=True, admin=True)
            if connection.scalar(text("SELECT count(*) FROM users")) >= 5:
                raise AuthError(
                    409, "registration_full", "This cloud has reached its account limit"
                )
            now = self.clock()
            if (
                connection.scalar(
                    text("""SELECT count(*) FROM invitations WHERE redeemed_at IS NULL
                AND revoked_at IS NULL AND expires_at>:now"""),
                    {"now": now},
                )
                >= 20
            ):
                raise AuthError(409, "invitation_limit", "Revoke an unused invitation first")
            value, identifier = token(), uuid.uuid4()
            expires = now + timedelta(hours=24)
            connection.execute(
                text("""INSERT INTO invitations
                (id,token_hash,created_by,created_at,expires_at)
                VALUES (:id,:hash,:actor,:now,:expires)"""),
                {
                    "id": identifier,
                    "hash": digest(value),
                    "actor": actor["id"],
                    "now": now,
                    "expires": expires,
                },
            )
            self.audit(connection, actor["id"], "invitation_create", identifier, request_id)
            return {"id": identifier, "token": value, "expires_at": expires}

    def revoke_invitation(self, session_token, csrf, identifier, request_id):
        with self.engine.begin() as connection:
            lock(connection)
            actor = self.actor(connection, session_token, csrf, mutation=True, admin=True)
            changed = connection.execute(
                text("""UPDATE invitations SET revoked_at=:now
                WHERE id=:id AND revoked_at IS NULL AND redeemed_at IS NULL RETURNING id"""),
                {"now": self.clock(), "id": identifier},
            ).scalar()
            if changed is None:
                raise AuthError(404, "invitation_unavailable", "Invitation unavailable")
            self.audit(connection, actor["id"], "invitation_revoke", identifier, request_id)

    def users(self, session_token):
        with self.engine.begin() as connection:
            self.actor(connection, session_token, admin=True)
            return [
                public_user(row)
                for row in connection.execute(
                    text("SELECT id,email,role,active,theme FROM users ORDER BY created_at,id")
                ).mappings()
            ]

    def change_user(self, session_token, csrf, identifier, request_id, deactivate):
        with self.engine.begin() as connection:
            lock(connection)
            actor = self.actor(connection, session_token, csrf, mutation=True, admin=True)
            if identifier == actor["id"]:
                raise AuthError(409, "self_change_blocked", "Use sign out for your own session")
            target = (
                connection.execute(
                    text("SELECT id,role,active FROM users WHERE id=:id"), {"id": identifier}
                )
                .mappings()
                .first()
            )
            if target is None:
                raise AuthError(404, "account_unavailable", "Account unavailable")
            if deactivate and target["role"] == "admin" and target["active"]:
                count = connection.scalar(
                    text("SELECT count(*) FROM users WHERE role='admin' AND active")
                )
                if count <= 1:
                    raise AuthError(409, "last_admin", "Keep an active administrator")
            if deactivate:
                connection.execute(
                    text("UPDATE users SET active=false WHERE id=:id"), {"id": identifier}
                )
            connection.execute(
                text("UPDATE sessions SET revoked_at=:now WHERE user_id=:id"),
                {"now": self.clock(), "id": identifier},
            )
            self.audit(
                connection,
                actor["id"],
                "user_deactivate" if deactivate else "session_revoke",
                identifier,
                request_id,
            )

    def theme(self, session_token, csrf, value):
        with self.engine.begin() as connection:
            lock(connection)
            actor = self.actor(connection, session_token, csrf, mutation=True)
            connection.execute(
                text("UPDATE users SET theme=:theme WHERE id=:id"),
                {"theme": value, "id": actor["id"]},
            )
