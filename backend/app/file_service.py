"""Locked namespace operations, quota reservations and durable deletion journals."""

import json
import secrets
import uuid
from contextlib import contextmanager
from datetime import timedelta

from sqlalchemy import text

from app.file_models import FILE_ACTIONS, FILE_LIMIT, ROOT_ID, ItemView, fail
from app.file_store import FileStore
from app.identity_security import AuthError, valid_token
from app.identity_service import lock

ACTIVE = "('reserved','streaming','finalizing')"
COLUMNS = """SELECT i.*, b.size_bytes,b.checksum_sha256,b.storage_key,b.state AS blob_state
             FROM items i LEFT JOIN blobs b ON b.id=i.blob_id"""


def advisory_key(identifier):
    return identifier.int % (2**63)


class Files:
    def __init__(self, engine, identity, settings):
        self.engine, self.identity, self.settings = engine, identity, settings
        self.store = FileStore(settings.storage_root)

    @contextmanager
    def transaction(self, session, csrf=None, *, mutation=False, admin=False):
        if not valid_token(session):
            fail("authentication_required", "Please sign in", 401)
        with self.engine.begin() as connection:
            lock(connection)
            actor = self.identity.actor(connection, session, csrf, mutation=mutation, admin=admin)
            yield connection, actor

    def raw(self, connection, identifier):
        row = (
            connection.execute(text(COLUMNS + " WHERE i.id=:id"), {"id": identifier})
            .mappings()
            .first()
        )
        if row is None:
            fail()
        return row

    def ancestors(self, connection, identifier, *, allow_trashed=False):
        result, seen = [], set()
        while identifier is not None:
            if identifier in seen or len(result) > 64:
                fail("invalid_tree", "Folder nesting is unavailable", 409)
            row = self.raw(connection, identifier)
            if row["deletion_job_id"] or (row["trashed_at"] and not (allow_trashed and not result)):
                fail()
            seen.add(identifier)
            result.append(row)
            identifier = row["parent_id"]
        if not result or result[-1]["id"] != ROOT_ID:
            fail()
        return result

    def live(self, connection, identifier):
        return self.ancestors(connection, identifier)[0]

    def directory(self, connection, identifier):
        ancestors = self.ancestors(connection, identifier)
        if ancestors[0]["kind"] != "folder":
            fail("invalid_parent", "Choose a live destination folder", 409)
        return ancestors

    def view(self, row):
        return {
            **{key: row[key] for key in ItemView.model_fields if key != "has_icon"},
            "has_icon": row["icon_blob_id"] is not None,
        }

    def revision(self, row, revision):
        if row["id"] == ROOT_ID:
            fail("protected_root", "The root folder cannot be changed", 409)
        if row["revision"] != revision:
            fail("revision_conflict", "This item changed. Refresh before trying again", 409)

    def audit(self, connection, actor, action, item, request_id, details=None):
        connection.execute(
            text("""INSERT INTO activity
            (id,actor_id,action,target_id,target_name,request_id,details)
            VALUES (:id,:actor,:action,:target,:name,:request,CAST(:details AS jsonb))"""),
            {
                "id": uuid.uuid4(),
                "actor": actor,
                "action": action,
                "target": item["id"],
                "name": item["name"],
                "request": request_id,
                "details": json.dumps(details or {}),
            },
        )

    def collision(self, connection, parent, name, choice, exclude=None):
        def found(candidate):
            return (
                connection.execute(
                    text("""SELECT id,kind,revision FROM items WHERE parent_id=:parent
                AND name_key=:key AND trashed_at IS NULL
                AND (CAST(:exclude AS uuid) IS NULL OR id<>CAST(:exclude AS uuid))"""),
                    {"parent": parent, "key": candidate.casefold(), "exclude": exclude},
                )
                .mappings()
                .first()
            )

        other = found(name)
        if other and choice == "error":
            fail("name_conflict", "An item with this name already exists", 409)
        if other and choice == "keep_both":
            stem, dot, extension = name.rpartition(".")
            if not dot or not stem:
                stem, extension, dot = name, "", ""
            for number in range(1, 10001):
                suffix = f" ({number})" + dot + extension
                # Preserve the byte bound even for multibyte names/long extensions.
                if len(suffix.encode()) > 120:
                    suffix = f" ({number})"
                candidate_stem = stem
                while len((candidate_stem + suffix).encode()) > 255:
                    candidate_stem = candidate_stem[:-1]
                candidate = candidate_stem + suffix
                if not found(candidate):
                    return candidate, None
            fail("name_conflict", "Too many copies with this name", 409)
        return name, other

    def get(self, session, identifier):
        with self.transaction(session) as (connection, _):
            return self.view(self.live(connection, identifier))

    def browse(self, session, parent, limit=100, offset=0, query=""):
        with self.transaction(session) as (connection, _):
            self.directory(connection, parent)
            rows = connection.execute(
                text(
                    COLUMNS
                    + """ WHERE i.parent_id=:parent
                AND i.trashed_at IS NULL AND i.deletion_job_id IS NULL
                AND strpos(i.name_key,:query)>0 ORDER BY i.name_key,i.id
                LIMIT :limit OFFSET :offset"""
                ),
                {"parent": parent, "query": query.casefold(), "limit": limit, "offset": offset},
            ).mappings()
            return [self.view(row) for row in rows]

    def folder(self, session, csrf, data, request_id):
        with self.transaction(session, csrf, mutation=True) as (connection, actor):
            if len(self.directory(connection, data.parent_id)) > 64:
                fail("nesting_limit", "Use fewer nested folders", 409)
            name, _ = self.collision(connection, data.parent_id, data.name, data.collision)
            identifier = uuid.uuid4()
            connection.execute(
                text("""INSERT INTO items (id,parent_id,kind,name,name_key,uploader_id)
                VALUES (:id,:parent,'folder',:name,:key,:actor)"""),
                {
                    "id": identifier,
                    "parent": data.parent_id,
                    "name": name,
                    "key": name.casefold(),
                    "actor": actor["id"],
                },
            )
            row = self.raw(connection, identifier)
            self.audit(connection, actor["id"], "folder_create", row, request_id)
            return self.view(row)

    def subtree(self, connection, identifier):
        rows = (
            connection.execute(
                text("""WITH RECURSIVE tree AS (
            SELECT id,0 AS depth,ARRAY[id] AS path FROM items WHERE id=:id
            UNION ALL SELECT i.id,t.depth+1,t.path||i.id
            FROM items i JOIN tree t ON i.parent_id=t.id
            WHERE t.depth<65 AND NOT i.id=ANY(t.path))
            SELECT id,depth FROM tree LIMIT 10001"""),
                {"id": identifier},
            )
            .mappings()
            .all()
        )
        if len(rows) > 10000 or any(row["depth"] > 64 for row in rows):
            fail(
                "operation_limit",
                "This folder is too large or deeply nested for one operation",
                409,
            )
        return rows

    def move(self, session, csrf, identifier, data, request_id, *, restore=False):
        with self.transaction(session, csrf, mutation=True) as (connection, actor):
            row = self.raw(connection, identifier) if restore else self.live(connection, identifier)
            self.revision(row, data.expected_revision)
            if row["deletion_job_id"] or (restore and not row["trashed_at"]):
                fail()
            parent = data.parent_id or row["parent_id"]
            try:
                ancestors = self.directory(connection, parent)
            except AuthError:
                if restore:
                    fail("restore_destination_required", "Choose a live destination folder", 409)
                raise
            descendants = self.subtree(connection, identifier)
            if identifier in {item["id"] for item in ancestors}:
                fail("folder_cycle", "A folder cannot be moved inside itself", 409)
            if len(ancestors) + max(item["depth"] for item in descendants) > 64:
                fail("nesting_limit", "Use fewer nested folders", 409)
            name, _ = self.collision(
                connection, parent, data.name or row["name"], data.collision, identifier
            )
            moved, renamed = parent != row["parent_id"], name != row["name"]
            if not (moved or renamed or restore):
                return self.view(row)
            connection.execute(
                text("""UPDATE items SET parent_id=:parent,name=:name,name_key=:key,
                trashed_at=NULL,trashed_by=NULL,revision=revision+1,updated_at=now()
                WHERE id=:id"""),
                {"id": identifier, "parent": parent, "name": name, "key": name.casefold()},
            )
            if moved:
                connection.execute(
                    text("DELETE FROM positions WHERE item_id=:id"), {"id": identifier}
                )
            result = self.raw(connection, identifier)
            if restore:
                self.audit(connection, actor["id"], "restore", result, request_id)
            else:
                for action, changed in [("rename", renamed), ("move", moved)]:
                    if changed:
                        self.audit(connection, actor["id"], action, result, request_id)
            return self.view(result)

    def trash(self, session, csrf, identifier, data, request_id):
        with self.transaction(session, csrf, mutation=True) as (connection, actor):
            row = self.live(connection, identifier)
            self.revision(row, data.expected_revision)
            self.subtree(connection, identifier)
            connection.execute(
                text("""UPDATE items SET trashed_at=now(),trashed_by=:actor,
                revision=revision+1,updated_at=now() WHERE id=:id"""),
                {"id": identifier, "actor": actor["id"]},
            )
            self.audit(connection, actor["id"], "trash", row, request_id)
            return self.view(self.raw(connection, identifier))

    def trash_list(self, session, limit=100, offset=0):
        with self.transaction(session) as (connection, _):
            rows = connection.execute(
                text(
                    COLUMNS
                    + """ WHERE i.trashed_at IS NOT NULL
                AND i.deletion_job_id IS NULL ORDER BY i.trashed_at DESC,i.id
                LIMIT :limit OFFSET :offset"""
                ),
                {"limit": limit, "offset": offset},
            ).mappings()
            return [self.view(row) for row in rows]

    def capacity(self, connection):
        used = connection.scalar(
            text("SELECT coalesce(sum(size_bytes),0) FROM blobs WHERE state<>'staging'")
        )
        reserved = connection.scalar(
            text(
                "SELECT coalesce(sum(reserved_bytes),0) FROM upload_reservations "
                f"WHERE state IN {ACTIVE}"
            )
        )
        remaining = connection.scalar(
            text(
                "SELECT coalesce(sum(reserved_bytes-received_bytes),0) FROM upload_reservations "
                f"WHERE state IN {ACTIVE}"
            )
        )
        return int(used), int(reserved), int(remaining)

    def storage(self, session):
        with self.transaction(session) as (connection, _):
            used, reserved, remaining = self.capacity(connection)
            available = max(
                0,
                min(
                    self.settings.storage_pool_bytes - used - reserved,
                    self.store.free() - self.settings.storage_reserve_bytes - remaining,
                ),
            )
            percent = (used + reserved) * 100 / self.settings.storage_pool_bytes
            return {
                "used_bytes": used,
                "reserved_bytes": reserved,
                "pool_bytes": self.settings.storage_pool_bytes,
                "available_bytes": available,
                "warning_percent": 90 if percent >= 90 else 80 if percent >= 80 else None,
            }

    def reserve(self, session, csrf, data, request_id):
        if data.collision == "cancel":
            # Caller has authenticated before parsing; cancellation creates no durable records.
            fail("upload_cancelled", "Upload canceled", 409)
        with self.transaction(session, csrf, mutation=True) as (connection, actor):
            self.directory(connection, data.parent_id)
            _, other = self.collision(connection, data.parent_id, data.name, data.collision)
            if data.collision == "replace":
                if (
                    not data.confirm_replace
                    or not other
                    or other["kind"] != "file"
                    or other["id"] != data.target_id
                    or other["revision"] != data.expected_revision
                ):
                    fail(
                        "replacement_conflict",
                        "Confirm replacement of the current file revision",
                        409,
                    )
            elif (
                data.target_id is not None
                or data.expected_revision is not None
                or data.confirm_replace
            ):
                fail("invalid_request", "Replacement fields require Replace", 422)
            count = connection.scalar(
                text(f"SELECT count(*) FROM upload_reservations WHERE state IN {ACTIVE}")
            )
            own = connection.scalar(
                text(
                    "SELECT count(*) FROM upload_reservations "
                    f"WHERE state IN {ACTIVE} AND user_id=:id"
                ),
                {"id": actor["id"]},
            )
            if count >= 4 or own >= 2:
                fail("upload_busy", "Wait for another upload to finish", 429)
            used, reserved, remaining = self.capacity(connection)
            if used + reserved + data.size_bytes > self.settings.storage_pool_bytes:
                fail("storage_full", "The shared storage pool is full", 507)
            if (
                self.store.free() - remaining - data.size_bytes
                < self.settings.storage_reserve_bytes
            ):
                fail("disk_reserve", "Insufficient safe disk space for this upload", 507)
            blob, identifier, key = uuid.uuid4(), uuid.uuid4(), secrets.token_hex(32)
            connection.execute(
                text("""INSERT INTO blobs(id,storage_key,size_bytes,checksum_sha256,state)
                VALUES (:id,:key,0,:hash,'staging')"""),
                {"id": blob, "key": key, "hash": "0" * 64},
            )
            connection.execute(
                text("""INSERT INTO upload_reservations
                (id,user_id,parent_id,blob_id,reserved_bytes,state,expires_at,intent)
                VALUES (:id,:actor,:parent,:blob,:size,'reserved',
                :expires,CAST(:intent AS jsonb))"""),
                {
                    "id": identifier,
                    "actor": actor["id"],
                    "parent": data.parent_id,
                    "blob": blob,
                    "size": data.size_bytes,
                    "expires": self.identity.clock() + timedelta(hours=2),
                    "intent": data.model_dump_json(),
                },
            )
            return {
                "id": identifier,
                "blob_id": blob,
                "key": key,
                "user_id": actor["id"],
                "size": data.size_bytes,
                "intent": data,
                "request_id": request_id,
            }

    def finish(self, session, csrf, reservation, size, checksum):
        data = reservation["intent"]
        with self.transaction(session, csrf, mutation=True) as (connection, actor):
            record = (
                connection.execute(
                    text("SELECT * FROM upload_reservations WHERE id=:id"),
                    {"id": reservation["id"]},
                )
                .mappings()
                .first()
            )
            if (
                not record
                or record["state"] not in ("reserved", "streaming")
                or record["user_id"] != actor["id"]
            ):
                fail("upload_unavailable", "Upload is no longer available", 409)
            if (
                record["expires_at"] <= self.identity.clock()
                or size != data.size_bytes
                or size > FILE_LIMIT
            ):
                fail("size_mismatch", "File size did not match the upload declaration", 422)
            self.directory(connection, data.parent_id)
            name, other = self.collision(connection, data.parent_id, data.name, data.collision)
            if data.collision == "replace":
                if (
                    not other
                    or other["id"] != data.target_id
                    or other["revision"] != data.expected_revision
                ):
                    fail(
                        "replacement_conflict", "The replacement target changed during upload", 409
                    )
                row = self.live(connection, other["id"])
                recovery = uuid.uuid4()
                connection.execute(
                    text("""INSERT INTO items
                    (id,parent_id,kind,name,name_key,uploader_id,blob_id,icon_blob_id,
                    trashed_at,trashed_by,replacement_of)
                    VALUES (:id,:parent,'file',:name,:key,:uploader,:blob,:icon,
                    now(),:actor,:original)"""),
                    {
                        "id": recovery,
                        "parent": row["parent_id"],
                        "name": row["name"],
                        "key": row["name_key"],
                        "uploader": row["uploader_id"],
                        "blob": row["blob_id"],
                        "icon": row["icon_blob_id"],
                        "actor": actor["id"],
                        "original": row["id"],
                    },
                )
                identifier = row["id"]
                connection.execute(
                    text("""UPDATE items SET blob_id=:blob,uploader_id=:actor,
                    revision=revision+1,updated_at=now() WHERE id=:id"""),
                    {"id": identifier, "blob": reservation["blob_id"], "actor": actor["id"]},
                )
            else:
                identifier = uuid.uuid4()
                connection.execute(
                    text("""INSERT INTO items(id,parent_id,kind,name,name_key,uploader_id,blob_id)
                    VALUES (:id,:parent,'file',:name,:key,:actor,:blob)"""),
                    {
                        "id": identifier,
                        "parent": data.parent_id,
                        "name": name,
                        "key": name.casefold(),
                        "actor": actor["id"],
                        "blob": reservation["blob_id"],
                    },
                )
            # Failure before/after rename leaves the previous visible version untouched on rollback.
            self.store.publish(reservation["key"])
            connection.execute(
                text("""UPDATE blobs SET size_bytes=:size,checksum_sha256=:hash,state='durable'
                WHERE id=:id"""),
                {"id": reservation["blob_id"], "size": size, "hash": checksum},
            )
            connection.execute(
                text("""UPDATE upload_reservations SET received_bytes=:size,state='complete'
                WHERE id=:id"""),
                {"id": reservation["id"], "size": size},
            )
            result = self.raw(connection, identifier)
            details = {"recovery_item_id": str(recovery)} if data.collision == "replace" else {}
            self.audit(
                connection,
                actor["id"],
                "replace" if data.collision == "replace" else "upload",
                result,
                reservation["request_id"],
                details,
            )
            return self.view(result)

    def abandon(self, reservation):
        # Never unlink after uncertain commit unless a fresh DB transaction proves no reference.
        with self.engine.begin() as connection:
            lock(connection)
            blob = reservation["blob_id"]
            if connection.scalar(
                text("SELECT 1 FROM items WHERE blob_id=:id OR icon_blob_id=:id LIMIT 1"),
                {"id": blob},
            ):
                return
            self.store.discard(reservation["key"])
            connection.execute(
                text("UPDATE upload_reservations SET state='aborted' WHERE blob_id=:id"),
                {"id": blob},
            )
            connection.execute(text("DELETE FROM blobs WHERE id=:id"), {"id": blob})

    def open_download(self, session, identifier):
        with self.transaction(session) as (connection, actor):
            row = self.live(connection, identifier)
            if row["kind"] != "file" or row["blob_state"] != "durable":
                fail()
            try:
                stream = self.store.open(row["storage_key"], row["size_bytes"])
            except OSError:
                fail("content_unavailable", "File contents are temporarily unavailable", 503)
            return stream, self.view(row), actor["id"]

    def downloaded(self, actor, item, request_id, complete):
        with self.engine.begin() as connection:
            self.audit(
                connection,
                actor,
                "download",
                item,
                request_id,
                {"server_stream": "complete" if complete else "interrupted"},
            )

    def activity(self, session, limit=100, offset=0):
        with self.transaction(session) as (connection, _):
            return [
                dict(row)
                for row in connection.execute(
                    text("""SELECT id,actor_id,action,target_id,
                target_name,occurred_at,details FROM activity WHERE action=ANY(:actions)
                ORDER BY occurred_at DESC,id LIMIT :limit OFFSET :offset"""),
                    {"actions": list(FILE_ACTIONS), "limit": limit, "offset": offset},
                ).mappings()
            ]

    def delete(self, session, csrf, identifier, data, request_id):
        with self.transaction(session, csrf, mutation=True, admin=True) as (connection, actor):
            row = self.raw(connection, identifier)
            self.revision(row, data.expected_revision)
            if not row["trashed_at"] or row["deletion_job_id"]:
                fail("deletion_conflict", "Choose an available item in the recycle bin", 409)
            descendants = self.subtree(connection, identifier)
            identifiers = [child["id"] for child in descendants]
            if connection.scalar(
                text(
                    "SELECT 1 FROM items WHERE id=ANY(:ids) AND deletion_job_id IS NOT NULL LIMIT 1"
                ),
                {"ids": identifiers},
            ):
                fail("deletion_conflict", "A nested deletion is still pending", 409)
            candidates = (
                connection.execute(
                    text("""SELECT DISTINCT b.id FROM blobs b JOIN items i
                ON (i.blob_id=b.id OR i.icon_blob_id=b.id) WHERE i.id=ANY(:ids)
                AND NOT EXISTS (SELECT 1 FROM items other WHERE
                (other.blob_id=b.id OR other.icon_blob_id=b.id) AND NOT other.id=ANY(:ids))"""),
                    {"ids": identifiers},
                )
                .scalars()
                .all()
            )
            job = uuid.uuid4()
            connection.execute(
                text("""INSERT INTO deletion_jobs
                (id,target_id,target_name,actor_id,request_id,blob_ids,item_count)
                VALUES (:id,:target,:name,:actor,:request,:blobs,:count)"""),
                {
                    "id": job,
                    "target": identifier,
                    "name": row["name"],
                    "actor": actor["id"],
                    "request": request_id,
                    "blobs": candidates,
                    "count": len(identifiers),
                },
            )
            connection.execute(
                text("UPDATE items SET deletion_job_id=:job WHERE id=ANY(:ids)"),
                {"job": job, "ids": identifiers},
            )
            connection.execute(
                text("UPDATE blobs SET state='deleting' WHERE id=ANY(:ids)"), {"ids": candidates}
            )
        self.process_deletion(job)
        return self.job(session, job)

    def job(self, session, identifier):
        with self.transaction(session, admin=True) as (connection, _):
            row = (
                connection.execute(
                    text("""SELECT id,target_id,state,last_error,item_count,created_at,completed_at
                FROM deletion_jobs WHERE id=:id"""),
                    {"id": identifier},
                )
                .mappings()
                .first()
            )
            if not row:
                fail()
            return dict(row)

    def process_deletion(self, identifier):
        with self.engine.begin() as connection:
            lock(connection)
            job = (
                connection.execute(
                    text("SELECT * FROM deletion_jobs WHERE id=:id AND state='pending'"),
                    {"id": identifier},
                )
                .mappings()
                .first()
            )
            if not job:
                return
            blobs = (
                connection.execute(
                    text("SELECT id,storage_key FROM blobs WHERE id=ANY(:ids)"),
                    {"ids": job["blob_ids"]},
                )
                .mappings()
                .all()
            )
            # Check again before any irreversible filesystem action.
            if connection.scalar(
                text("""SELECT 1 FROM items WHERE (blob_id=ANY(:ids) OR icon_blob_id=ANY(:ids))
                AND deletion_job_id IS DISTINCT FROM :job LIMIT 1"""),
                {"ids": job["blob_ids"], "job": identifier},
            ):
                return
            try:
                for blob in blobs:
                    self.store.discard(blob["storage_key"])
            except OSError:
                connection.execute(
                    text("UPDATE deletion_jobs SET last_error='storage_unavailable' WHERE id=:id"),
                    {"id": identifier},
                )
                return
            connection.execute(
                text(
                    "DELETE FROM positions WHERE item_id IN "
                    "(SELECT id FROM items WHERE deletion_job_id=:job)"
                ),
                {"job": identifier},
            )
            connection.execute(
                text("DELETE FROM items WHERE deletion_job_id=:job"), {"job": identifier}
            )
            connection.execute(
                text("DELETE FROM blobs WHERE id=ANY(:ids)"), {"ids": job["blob_ids"]}
            )
            self.audit(
                connection,
                job["actor_id"],
                "permanent_delete",
                {"id": job["target_id"], "name": job["target_name"]},
                job["request_id"],
                {"item_count": job["item_count"]},
            )
            connection.execute(
                text(
                    "UPDATE deletion_jobs SET state='complete',last_error=NULL,completed_at=now() "
                    "WHERE id=:id"
                ),
                {"id": identifier},
            )

    def reconcile(self):
        from app.file_media import clean_retired_icons

        clean_retired_icons(self)
        # Only abandoned unpublished bytes and previously confirmed jobs; never auto-purge trash.
        with self.engine.begin() as connection:
            lock(connection)
            rows = (
                connection.execute(
                    text("""SELECT b.id,b.storage_key FROM blobs b WHERE b.state='staging'
                AND NOT EXISTS (SELECT 1 FROM items WHERE blob_id=b.id OR icon_blob_id=b.id)
                AND b.created_at<:before LIMIT 100"""),
                    {"before": self.identity.clock() - timedelta(hours=2)},
                )
                .mappings()
                .all()
            )
            for blob in rows:
                acquired = connection.scalar(
                    text("SELECT pg_try_advisory_xact_lock(:key)"),
                    {"key": advisory_key(blob["id"])},
                )
                if not acquired:
                    continue
                try:
                    self.store.discard(blob["storage_key"])
                except OSError:
                    continue
                connection.execute(
                    text("UPDATE upload_reservations SET state='aborted' WHERE blob_id=:id"),
                    {"id": blob["id"]},
                )
                connection.execute(text("DELETE FROM blobs WHERE id=:id"), {"id": blob["id"]})
            pending = (
                connection.execute(
                    text(
                        "SELECT id FROM deletion_jobs WHERE state='pending' "
                        "ORDER BY created_at LIMIT 20"
                    )
                )
                .scalars()
                .all()
            )
        for job in pending:
            self.process_deletion(job)
