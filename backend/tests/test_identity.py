"""Identity acceptance against a harness-owned disposable PostgreSQL database only."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.config import Settings
from app.identity_security import AuthError, RegisterInput, digest
from app.main import create_app, logger

PASSWORD = "Synthetic integration passphrase 47!"
ORIGIN = {"Origin": "https://testserver", "Content-Type": "application/json"}


@pytest.fixture
def identity(tmp_path):
    url = os.environ.get("TEST_RUNTIME_DATABASE_URL")
    if not url:
        pytest.skip("Run scripts/verify_postgres.py for real identity acceptance")
    parsed = make_url(url)
    expected = os.environ.get("TEST_DISPOSABLE_DATABASE_NAME", "")
    if (
        not expected.startswith("cloud_test_")
        or parsed.database != expected
        or parsed.host != "127.0.0.1"
    ):
        pytest.fail("Refusing identity cleanup outside the harness-owned disposable database")
    engine = create_engine(url, hide_parameters=True)

    def cleanup():
        with engine.begin() as connection:
            for table in ("activity", "sessions", "invitations", "users", "auth_rate_limits"):
                connection.execute(text(f"DELETE FROM {table}"))

    cleanup()
    settings = Settings(_env_file=None, database_url=url, storage_root=tmp_path)
    application = create_app(settings)
    try:
        with TestClient(application, base_url="https://testserver") as client:
            service = application.state.identity
            admin = service.bootstrap("admin@example.com", PASSWORD)
            response = client.post(
                "/api/auth/login",
                json={"email": "admin@example.com", "password": PASSWORD},
                headers=ORIGIN,
            )
            assert response.status_code == 200, response.text
            yield client, service, engine, admin
    finally:
        cleanup()
        engine.dispose()


def csrf(client):
    return {**ORIGIN, "X-CSRF-Token": client.cookies["__Host-pc_csrf"]}


def invite(client):
    result = client.post("/api/admin/invitations", json={}, headers=csrf(client))
    assert result.status_code == 201, result.text
    return result.json()


def member(service, token, email="member@example.net"):
    return service.redeem(
        RegisterInput(email=email, password=PASSWORD, token=token),
        None,
        "synthetic-peer",
        uuid.uuid4(),
    )


def test_bootstrap_hashes_cookies_rotation_and_private_responses(identity):
    client, service, engine, _ = identity
    with pytest.raises(AuthError) as error:
        service.bootstrap("second@example.com", PASSWORD)
    assert error.value.status == 409
    old = client.cookies["__Host-pc_session"]
    response = client.post(
        "/api/auth/login", json={"email": "ADMIN@EXAMPLE.COM", "password": PASSWORD}, headers=ORIGIN
    )
    assert response.status_code == 200
    cookies = response.headers.get_list("set-cookie")
    assert len(cookies) == 2 and all(
        "Secure" in value and "SameSite=strict" in value for value in cookies
    )
    assert "HttpOnly" in cookies[0] and "HttpOnly" not in cookies[1]
    assert all("Domain=" not in value for value in cookies)
    assert client.cookies["__Host-pc_session"] != old
    with pytest.raises(AuthError):
        service.me(old)
    with engine.connect() as connection:
        hashed = connection.scalar(text("SELECT password_hash FROM users"))
        assert hashed.startswith("$argon2id$v=19$m=65536,t=3,p=1$")
        assert PASSWORD not in hashed
        assert (
            connection.scalar(
                text("SELECT count(*) FROM sessions WHERE token_hash=:hash"), {"hash": digest(old)}
            )
            == 1
        )
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert set(me.json()["user"]) == {"id", "email", "role", "active", "theme"}
    assert not any(value in me.text for value in ("password_hash", "token_hash", "csrf_hash", old))


def test_origin_csrf_content_type_size_validation_and_no_signup(identity):
    client, _, _, _ = identity
    assert client.post("/api/admin/invitations", json={}).status_code == 403
    assert (
        client.post(
            "/api/admin/invitations",
            json={},
            headers={**csrf(client), "Origin": "https://attacker.example"},
        ).status_code
        == 403
    )
    assert client.post("/api/admin/invitations", json={}, headers=ORIGIN).status_code == 403
    assert (
        client.post(
            "/api/admin/invitations",
            content="{}",
            headers={"Origin": "https://testserver", "Content-Type": "text/plain"},
        ).status_code
        == 415
    )
    assert client.post("/api/auth/login", content=b"x" * 17000, headers=ORIGIN).status_code == 413
    assert (
        client.post(
            "/api/auth/login", content=iter([b"x" * 9000, b"x" * 9000]), headers=ORIGIN
        ).status_code
        == 413
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": PASSWORD, "role": "admin"},
            headers=ORIGIN,
        ).status_code
        == 422
    )
    assert client.post("/api/auth/signup", json={}, headers=ORIGIN).status_code == 404
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "missing@example.com", "password": PASSWORD},
            headers=ORIGIN,
        ).json()["error"]["code"]
        == "invalid_credentials"
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "wrong"},
            headers=ORIGIN,
        ).json()["error"]["code"]
        == "invalid_credentials"
    )


def test_invitation_single_use_expiry_revocation_and_member_authorization(identity):
    client, service, engine, _ = identity
    created = invite(client)
    listed = client.get("/api/admin/invitations")
    assert created["token"] not in listed.text and "token_hash" not in listed.text
    with engine.connect() as connection:
        assert bytes(
            connection.scalar(
                text("SELECT token_hash FROM invitations WHERE id=:id"),
                {"id": uuid.UUID(created["id"])},
            )
        ) == digest(created["token"])
    payload, session, csrf_value = member(service, created["token"])
    assert payload["user"]["role"] == "member"
    with pytest.raises(AuthError) as error:
        member(service, created["token"], "another@example.com")
    assert error.value.code == "invitation_unavailable"
    with TestClient(client.app, base_url="https://testserver") as guest:
        guest.cookies.set("__Host-pc_session", session)
        for method, path in [
            ("GET", "/api/admin/users"),
            ("GET", "/api/admin/invitations"),
            ("POST", "/api/admin/invitations"),
        ]:
            response = guest.request(
                method,
                path,
                json={} if method == "POST" else None,
                headers={**ORIGIN, "X-CSRF-Token": csrf_value},
            )
            assert response.status_code == 403
    revoked = invite(client)
    assert (
        client.post(
            f"/api/admin/invitations/{revoked['id']}/revoke", json={}, headers=csrf(client)
        ).status_code
        == 204
    )
    with pytest.raises(AuthError):
        member(service, revoked["token"], "revoked@example.com")
    expired = invite(client)
    now = service.clock()
    service.clock = lambda: now + timedelta(hours=24)
    with pytest.raises(AuthError):
        member(service, expired["token"], "expired@example.com")


def test_logout_idle_absolute_expiry_and_theme(identity):
    client, service, engine, _ = identity
    session = client.cookies["__Host-pc_session"]
    assert (
        client.patch(
            "/api/users/me/preferences", json={"theme": "dark"}, headers=csrf(client)
        ).status_code
        == 204
    )
    assert client.get("/api/auth/me").json()["user"]["theme"] == "dark"
    now = service.clock()
    service.clock = lambda: now + timedelta(hours=25)
    assert client.get("/api/auth/me").status_code == 401
    assert "__Host-pc_session" not in client.cookies
    service.clock = lambda: now
    response = client.post(
        "/api/auth/login", json={"email": "admin@example.com", "password": PASSWORD}, headers=ORIGIN
    )
    assert response.status_code == 200
    absolute_token = client.cookies["__Host-pc_session"]
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE sessions SET idle_expires_at=:idle,absolute_expires_at=:absolute "
                "WHERE token_hash=:hash"
            ),
            {
                "idle": now + timedelta(days=9),
                "absolute": now + timedelta(days=7),
                "hash": digest(absolute_token),
            },
        )
    service.clock = lambda: now + timedelta(days=7, seconds=1)
    with pytest.raises(AuthError):
        service.me(absolute_token)
    service.clock = lambda: now
    assert client.post("/api/auth/logout", json={}, headers=csrf(client)).status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    with pytest.raises(AuthError):
        service.me(absolute_token)
    service.clock = lambda: now + timedelta(hours=25)
    with pytest.raises(AuthError):
        service.me(session)


def test_administrator_revoke_deactivate_and_self_protection(identity):
    client, service, _, admin = identity
    payload, session, _ = member(service, invite(client)["token"])
    identifier = payload["user"]["id"]
    assert (
        client.post(
            f"/api/admin/users/{identifier}/revoke-sessions", json={}, headers=csrf(client)
        ).status_code
        == 204
    )
    with pytest.raises(AuthError):
        service.me(session)
    assert (
        client.patch(
            f"/api/admin/users/{identifier}", json={"active": False}, headers=csrf(client)
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "member@example.net", "password": PASSWORD},
            headers=ORIGIN,
        ).status_code
        == 401
    )
    assert (
        client.patch(
            f"/api/admin/users/{admin['id']}", json={"active": False}, headers=csrf(client)
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/admin/users/{identifier}", json={"active": True}, headers=csrf(client)
        ).status_code
        == 422
    )
    assert len(client.get("/api/admin/users").json()) == 2


def test_concurrent_single_use_and_last_registration_slot(identity):
    client, service, engine, _ = identity
    value = invite(client)["token"]

    def compete(args):
        token_value, number = args
        try:
            member(service, token_value, f"person{number}@example.com")
            return 201
        except AuthError as error:
            return error.status

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(compete, [(value, 1), (value, 2)]))
    assert sorted(outcomes) == [201, 400]
    for number in (3, 4):
        member(service, invite(client)["token"], f"person{number}@example.com")
    values = [invite(client)["token"], invite(client)["token"]]
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(compete, [(values[0], 5), (values[1], 6)]))
    assert sorted(outcomes) == [201, 409]
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM users")) == 5
    assert client.post("/api/admin/invitations", json={}, headers=csrf(client)).status_code == 409


def test_rate_limits_persist_and_ignore_spoofed_forwarding(identity):
    client, service, engine, _ = identity
    for number in range(10):
        response = client.post(
            "/api/auth/login",
            json={"email": "absent@example.com", "password": "bad"},
            headers={**ORIGIN, "X-Forwarded-For": f"192.0.2.{number}"},
        )
        assert response.status_code == 401
    response = client.post(
        "/api/auth/login", json={"email": "absent@example.com", "password": "bad"}, headers=ORIGIN
    )
    assert response.status_code == 429 and response.headers["Retry-After"] == "900"
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT max(attempts) FROM auth_rate_limits")) >= 11
    now = service.clock()
    service.clock = lambda: now + timedelta(minutes=16)
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "absent@example.com", "password": "bad"},
            headers=ORIGIN,
        ).status_code
        == 401
    )


def test_sensitive_auth_data_absent_from_logs(identity, caplog):
    client, _, _, _ = identity
    logger.addHandler(caplog.handler)
    try:
        value = invite(client)["token"]
        response = client.post(
            "/api/auth/invitations/redeem",
            json={"email": "private-marker@example.net", "password": PASSWORD, "token": value},
            headers=ORIGIN,
        )
        assert response.status_code == 201
    finally:
        logger.removeHandler(caplog.handler)
    logs = "\n".join(record.getMessage() for record in caplog.records if record.name == logger.name)
    assert logs
    for private in (
        value,
        PASSWORD,
        "private-marker@example.net",
        client.cookies["__Host-pc_session"],
    ):
        assert private not in logs


def test_registration_validation_no_default_accounts_and_revoke_existing_session(identity):
    client, service, engine, admin = identity
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM users")) == 1
    invitation = invite(client)
    invalid = {"email": "guest@example.net", "password": "short", "token": invitation["token"]}
    assert (
        client.post("/api/auth/invitations/redeem", json=invalid, headers=ORIGIN).status_code == 422
    )
    invalid["password"] = PASSWORD
    invalid["role"] = "admin"
    assert (
        client.post("/api/auth/invitations/redeem", json=invalid, headers=ORIGIN).status_code == 422
    )
    del invalid["role"]
    assert client.get("/api/auth/me", headers={"Host": "attacker.example"}).status_code == 400
    with TestClient(client.app, base_url="https://testserver") as guest:
        assert guest.get("/api/admin/users").status_code == 401
        assert guest.post("/api/admin/invitations", json={}, headers=ORIGIN).status_code == 401
        registered = guest.post("/api/auth/invitations/redeem", json=invalid, headers=ORIGIN)
        assert registered.status_code == 201
        identifier = registered.json()["user"]["id"]
        assert guest.get("/api/auth/me").json()["user"]["role"] == "member"
        response = guest.patch(
            "/api/users/me/preferences", json={"theme": "dark"}, headers=csrf(client)
        )
        assert response.status_code == 403
        assert (
            client.patch(
                f"/api/admin/users/{identifier}", json={"active": False}, headers=csrf(client)
            ).status_code
            == 204
        )
        assert guest.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me").json()["user"]["id"] == str(admin["id"])
    with pytest.raises(AuthError):
        service.bootstrap("another@example.net", PASSWORD)


def test_peer_rate_budget_and_invitation_count_bound(identity):
    client, service, engine, _ = identity
    for _ in range(20):
        invite(client)
    assert client.post("/api/admin/invitations", json={}, headers=csrf(client)).status_code == 409
    for _ in range(30):
        service.limit("separate-peer", "redeem")
    with pytest.raises(AuthError) as error:
        service.limit("separate-peer", "redeem")
    assert error.value.status == 429
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM auth_rate_limits")) < 4096
