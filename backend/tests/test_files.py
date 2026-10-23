"""Storage integration on the identity harness's own disposable DB and tmp file root."""

import asyncio
import hashlib
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from sqlalchemy import text
from starlette.requests import ClientDisconnect
from test_identity import ORIGIN, PASSWORD, csrf, identity, invite, member  # noqa: F401

from app.file_models import FILE_LIMIT, ROOT_ID, MoveInput, UploadInput
from app.file_upload import Upload
from app.identity_security import AuthError


@pytest.fixture
def storage(request):
    client, service, engine, admin = request.getfixturevalue("identity")
    files = client.app.state.files
    files.settings.storage_reserve_bytes = 32 * 1024 * 1024
    try:
        yield client, files, engine, admin
    finally:
        # identity fixture already guards exact harness-owned loopback cloud_test_* DB.
        with engine.begin() as connection:
            for key in connection.execute(text("SELECT storage_key FROM blobs")).scalars():
                # Generated-key paths are confined to this fixture's own temporary file root.
                assert all(
                    path.resolve().is_relative_to(files.store.root)
                    for path in files.store.paths(key)
                )
                files.store.discard(key)
            connection.execute(text("DELETE FROM activity"))
            connection.execute(text("DELETE FROM positions"))
            connection.execute(text("DELETE FROM upload_reservations"))
            connection.execute(text("DELETE FROM items WHERE uploader_id IS NOT NULL"))
            connection.execute(text("DELETE FROM deletion_jobs"))
            connection.execute(
                text(
                    "DELETE FROM blobs WHERE NOT EXISTS "
                    "(SELECT 1 FROM items WHERE blob_id=blobs.id OR icon_blob_id=blobs.id)"
                )
            )


def upload(client, name="test.bin", payload=b"hello\x00\xffworld", **kwargs):
    metadata = {"name": name, "size_bytes": len(payload), **kwargs}
    return client.post(
        "/api/uploads",
        files=[
            ("metadata", (None, json.dumps(metadata), "application/json")),
            ("file", ("ignored-untrusted-name.exe", payload, "application/octet-stream")),
        ],
        headers={key: value for key, value in csrf(client).items() if key != "Content-Type"},
    )


def folder(client, name="folder", parent_id=str(ROOT_ID)):
    response = client.post(
        "/api/folders", json={"name": name, "parent_id": parent_id}, headers=csrf(client)
    )
    assert response.status_code == 201, response.text
    return response.json()


def mutate(client, item, action, **kwargs):
    return client.post(
        f"/api/items/{item['id']}/{action}",
        json={"expected_revision": item["revision"], **kwargs},
        headers=csrf(client),
    )


def tokens(client):
    return client.cookies["__Host-pc_session"], client.cookies["__Host-pc_csrf"]


def receiver(client, files, metadata, auth=None):
    session, csrf_value = auth or tokens(client)
    item = Upload(files, session, csrf_value, uuid.uuid4(), "multipart/form-data; boundary=testing")
    prefix = (
        b'--testing\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'
        + json.dumps(metadata).encode()
        + b'\r\n--testing\r\nContent-Disposition: form-data; name="file"; '
        b'filename="ignored"\r\n\r\n'
    )
    item.feed(prefix)
    return item


def test_roundtrip_attachment_metadata_and_no_security_activity(storage):
    client, files, engine, _ = storage
    payload = os.urandom(130003) + b"<script>inert bytes</script>"
    response = upload(client, "report.html", payload)
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["size_bytes"] == len(payload)
    assert item["checksum_sha256"] == hashlib.sha256(payload).hexdigest()
    assert "storage_key" not in response.text and "blob_id" not in response.text
    result = client.get(f"/api/items/{item['id']}/download")
    assert result.status_code == 200 and result.content == payload
    assert result.headers["content-type"] == "application/octet-stream"
    assert result.headers["content-disposition"].startswith("attachment;")
    assert result.headers["content-security-policy"].startswith("sandbox")
    assert item["id"] in {row["id"] for row in client.get("/api/items").json()}
    assert client.get("/api/storage").json()["used_bytes"] == len(payload)
    activity = client.get("/api/activity").json()
    assert {event["action"] for event in activity} == {"upload", "download"}
    assert (
        next(event for event in activity if event["action"] == "download")["details"][
            "server_stream"
        ]
        == "complete"
    )
    with engine.connect() as connection:
        key = connection.scalar(text("SELECT storage_key FROM blobs"))
    assert files.store.paths(key)[1].read_bytes() == payload


def test_replace_recovery_keep_both_cancel_and_stale_replacement(storage):
    client, _, _, _ = storage
    first = upload(client, "file.dat", b"old contents").json()
    assert upload(client, "FILE.DAT", b"collision").status_code == 409
    assert upload(client, "file.dat", b"cancel", collision="cancel").status_code == 409
    copy = upload(client, "FILE.DAT", b"copy", collision="keep_both")
    assert copy.status_code == 201 and copy.json()["name"] == "FILE (1).DAT"
    assert (
        upload(
            client,
            "file.dat",
            b"new",
            collision="replace",
            target_id=first["id"],
            expected_revision=first["revision"],
        ).status_code
        == 409
    )
    replacement = upload(
        client,
        "file.dat",
        b"new contents",
        collision="replace",
        target_id=first["id"],
        expected_revision=first["revision"],
        confirm_replace=True,
    )
    assert replacement.status_code == 201, replacement.text
    assert replacement.json()["id"] == first["id"] and replacement.json()["revision"] == 2
    assert (
        upload(
            client,
            "file.dat",
            b"stale",
            collision="replace",
            target_id=first["id"],
            expected_revision=1,
            confirm_replace=True,
        ).status_code
        == 409
    )
    recovery = client.get("/api/trash").json()[0]
    assert recovery["replacement_of"] == first["id"]
    restored = mutate(client, recovery, "restore", name="recovered.dat")
    assert restored.status_code == 200, restored.text
    assert client.get(f"/api/items/{recovery['id']}/download").content == b"old contents"
    assert client.get("/api/storage").json()["used_bytes"] == len(b"old contentsnew contentscopy")


def test_move_cycles_root_stale_revision_subtree_trash_and_restore(storage):
    client, _, _, _ = storage
    parent = folder(client, "parent")
    nested = folder(client, "nested", parent["id"])
    child = upload(client, "child.bin", b"child", parent_id=nested["id"]).json()
    cycle = client.patch(
        f"/api/items/{parent['id']}",
        json={"expected_revision": 1, "parent_id": nested["id"]},
        headers=csrf(client),
    )
    assert cycle.status_code == 409
    assert (
        client.patch(
            f"/api/items/{ROOT_ID}",
            json={"expected_revision": 1, "name": "rename-root"},
            headers=csrf(client),
        ).status_code
        == 409
    )
    changed = client.patch(
        f"/api/items/{child['id']}",
        json={"expected_revision": 1, "name": "renamed.bin", "parent_id": parent["id"]},
        headers=csrf(client),
    )
    assert changed.status_code == 200
    assert (
        client.patch(
            f"/api/items/{child['id']}",
            json={"expected_revision": 1, "name": "stale"},
            headers=csrf(client),
        ).status_code
        == 409
    )
    trashed = mutate(client, parent, "trash").json()
    assert client.get(f"/api/items/{child['id']}").status_code == 404
    assert client.get(f"/api/items/{child['id']}/download").status_code == 404
    assert client.get("/api/items", params={"parent_id": nested["id"]}).status_code == 404
    assert mutate(client, trashed, "restore").status_code == 200
    assert client.get(f"/api/items/{child['id']}").status_code == 200
    actions = {entry["action"] for entry in client.get("/api/activity").json()}
    assert {"folder_create", "rename", "move", "trash", "restore"} <= actions


def test_restore_missing_parent_and_name_conflict(storage):
    client, _, _, _ = storage
    parent = folder(client)
    child = upload(client, "child", b"x", parent_id=parent["id"]).json()
    child = mutate(client, child, "trash").json()
    parent = mutate(client, parent, "trash").json()
    assert mutate(client, child, "restore").status_code == 409
    assert mutate(client, child, "restore", parent_id=str(ROOT_ID)).status_code == 200
    new = upload(client, "folder", b"occupied").json()
    assert mutate(client, parent, "restore").status_code == 409
    restored = mutate(client, parent, "restore", collision="keep_both")
    assert restored.status_code == 200 and restored.json()["name"] == "folder (1)"
    assert client.get(f"/api/items/{new['id']}").status_code == 200


def test_authenticated_role_csrf_and_ancestor_access(storage):
    client, files, _, _ = storage
    created = upload(client).json()
    payload, session, csrf_value = member(files.identity, invite(client)["token"])
    with client.__class__(client.app, base_url="https://testserver") as guest:
        assert guest.get("/api/items").status_code == 401
        assert guest.get(f"/api/items/{created['id']}/download").status_code == 401
        guest.cookies.set("__Host-pc_session", session)
        assert guest.get(f"/api/items/{created['id']}/download").status_code == 200
        headers = {**ORIGIN, "X-CSRF-Token": csrf_value}
        trashed = guest.post(
            f"/api/items/{created['id']}/trash", json={"expected_revision": 1}, headers=headers
        ).json()
        denied = guest.request(
            "DELETE",
            f"/api/trash/{created['id']}",
            json={"expected_revision": trashed["revision"], "confirm": True},
            headers=headers,
        )
        assert denied.status_code == 403
        assert (
            guest.post("/api/folders", json={"name": "blocked"}, headers=ORIGIN).status_code == 403
        )
        assert (
            guest.post(
                "/api/folders",
                json={"name": "blocked"},
                headers={**headers, "Origin": "https://attacker.example"},
            ).status_code
            == 403
        )
    assert payload["user"]["role"] == "member"


@pytest.mark.parametrize(
    "name",
    [
        "../secret",
        "a/b",
        "a\\b",
        "..",
        " padded",
        "bad\nname",
        "bad\x00name",
        "x" * 256,
        "é" * 128,
        "bad.",
    ],
)
def test_invalid_names_rejected(storage, name):
    client, _, _, _ = storage
    assert client.post("/api/folders", json={"name": name}, headers=csrf(client)).status_code == 422


def test_quota_reservations_concurrency_warnings_and_disk_reserve(storage, monkeypatch):
    client, files, _, _ = storage
    session, csrf_value = tokens(client)
    files.settings.storage_pool_bytes = 100
    first = files.reserve(
        session, csrf_value, UploadInput(name="first", size_bytes=80), uuid.uuid4()
    )
    assert files.storage(session)["warning_percent"] == 80
    second = files.reserve(
        session, csrf_value, UploadInput(name="second", size_bytes=10), uuid.uuid4()
    )
    assert files.storage(session)["warning_percent"] == 90
    with pytest.raises(AuthError) as error:
        files.reserve(session, csrf_value, UploadInput(name="third", size_bytes=1), uuid.uuid4())
    assert error.value.status == 429
    files.abandon(second)
    with pytest.raises(AuthError) as error:
        files.reserve(session, csrf_value, UploadInput(name="third", size_bytes=21), uuid.uuid4())
    assert error.value.status == 507
    files.abandon(first)
    monkeypatch.setattr(files.store, "free", lambda: files.settings.storage_reserve_bytes + 2)
    assert upload(client, payload=b"too big").status_code == 507
    assert files.storage(session)["used_bytes"] == 0


def test_concurrent_upload_name_and_final_revision_races(storage):
    client, files, _, _ = storage
    first = receiver(client, files, {"name": "same", "size_bytes": 1})
    second = receiver(client, files, {"name": "same", "size_bytes": 1})
    first.feed(b"a\r\n--testing--\r\n")
    second.feed(b"b\r\n--testing--\r\n")

    def finish(item):
        success = False
        try:
            result = item.finish()
            success = True
            return result
        except AuthError as error:
            return error.status
        finally:
            item.close(success)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(finish, [first, second]))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert 409 in results
    original = next(result for result in results if isinstance(result, dict))
    replacing = receiver(
        client,
        files,
        {
            "name": "same",
            "size_bytes": 1,
            "collision": "replace",
            "target_id": str(original["id"]),
            "expected_revision": original["revision"],
            "confirm_replace": True,
        },
    )
    replacing.feed(b"c\r\n--testing--\r\n")
    session, csrf_value = tokens(client)
    files.move(
        session,
        csrf_value,
        original["id"],
        MoveInput(expected_revision=1, name="renamed"),
        uuid.uuid4(),
    )
    with pytest.raises(AuthError):
        replacing.finish()
    replacing.close()
    assert client.get(f"/api/items/{original['id']}/download").content in (b"a", b"b")


def test_interrupted_malformed_underflow_and_space_loss(storage, monkeypatch):
    client, files, _, _ = storage
    headers = {key: value for key, value in csrf(client).items() if key != "Content-Type"}
    headers["Content-Type"] = "multipart/form-data; boundary=testing"
    assert client.post("/api/uploads", content=b"--testing\r\n", headers=headers).status_code == 422
    item = receiver(client, files, {"name": "interrupted", "size_bytes": 5})
    item.feed(b"abc")
    item.close()
    assert client.get("/api/storage").json()["reserved_bytes"] == 0
    item = receiver(client, files, {"name": "underflow", "size_bytes": 5})
    item.feed(b"abc\r\n--testing--\r\n")
    with pytest.raises(AuthError) as error:
        item.finish()
    assert error.value.status == 422
    item.close()
    item = receiver(client, files, {"name": "space-loss", "size_bytes": 5})
    monkeypatch.setattr(files.store, "free", lambda: files.settings.storage_reserve_bytes)
    with pytest.raises(AuthError) as error:
        item.write(b"abc")
    assert error.value.status == 507
    item.close()


def test_filesystem_and_database_failure_preserve_previous_content(storage, monkeypatch):
    client, files, engine, _ = storage
    original = upload(client, "stable", b"old").json()

    def broken(*args):
        raise OSError("synthetic storage failure")

    with monkeypatch.context() as patch:
        patch.setattr(files.store, "publish", broken)
        failed = upload(
            client,
            "stable",
            b"new",
            collision="replace",
            target_id=original["id"],
            expected_revision=1,
            confirm_replace=True,
        )
        assert failed.status_code == 503
    assert client.get(f"/api/items/{original['id']}/download").content == b"old"
    before = files.audit

    def reject_audit(connection, actor, action, *args, **kwargs):
        if action == "replace":
            connection.execute(text("SELECT 1/0"))
        return before(connection, actor, action, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(files, "audit", reject_audit)
        failed = upload(
            client,
            "stable",
            b"new",
            collision="replace",
            target_id=original["id"],
            expected_revision=1,
            confirm_replace=True,
        )
        assert failed.status_code == 500
    assert client.get(f"/api/items/{original['id']}/download").content == b"old"
    assert client.get("/api/trash").json() == []
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM blobs WHERE state='staging'")) == 0


def test_delete_partial_failure_retry_subtree_and_no_auto_purge(storage, monkeypatch):
    client, files, engine, _ = storage
    parent = folder(client)
    upload(client, "inside", b"delete-me", parent_id=parent["id"])
    parent = mutate(client, parent, "trash").json()
    assert (
        client.request(
            "DELETE",
            f"/api/trash/{parent['id']}",
            json={"expected_revision": parent["revision"], "confirm": False},
            headers=csrf(client),
        ).status_code
        == 422
    )
    before = files.store.discard

    def fail_once(*args):
        raise OSError("synthetic unlink denied")

    with monkeypatch.context() as patch:
        patch.setattr(files.store, "discard", fail_once)
        response = client.request(
            "DELETE",
            f"/api/trash/{parent['id']}",
            json={"expected_revision": parent["revision"], "confirm": True},
            headers=csrf(client),
        )
        assert response.status_code == 200, response.text
        job = response.json()
        assert job["state"] == "pending" and job["last_error"] == "storage_unavailable"
    assert client.get("/api/storage").json()["used_bytes"] == len(b"delete-me")
    files.reconcile()
    assert client.get(f"/api/admin/deletions/{job['id']}").json()["state"] == "complete"
    assert client.get("/api/storage").json()["used_bytes"] == 0
    assert client.get(f"/api/items/{parent['id']}").status_code == 404
    assert any(
        event["action"] == "permanent_delete" for event in client.get("/api/activity").json()
    )
    keep = upload(client, "keep", b"keep").json()
    mutate(client, keep, "trash")
    files.reconcile()
    assert len(client.get("/api/trash").json()) == 1
    assert before
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT count(*) FROM items WHERE deletion_job_id IS NOT NULL"))
            == 0
        )


def test_reconcile_abandoned_renamed_bytes_skips_active_writer(storage):
    client, files, engine, _ = storage
    item = receiver(client, files, {"name": "abandoned", "size_bytes": 3})
    item.write(b"abc")
    blob = item.reservation["blob_id"]
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE blobs SET created_at=now()-interval '3 hours' WHERE id=:id"), {"id": blob}
        )
    files.reconcile()
    assert files.store.paths(item.reservation["key"])[0].exists()
    # Simulate process loss after fsync/rename but before metadata commit.
    item.stream.close()
    item.stream = None
    files.store.publish(item.reservation["key"])
    item.lease.execute(text("SELECT pg_advisory_unlock_all()"))
    item.lease.commit()
    item.lease.close()
    item.lease = None
    files.reconcile()
    assert not files.store.paths(item.reservation["key"])[1].exists()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM blobs WHERE id=:id"), {"id": blob}) == 0
    assert client.get("/api/storage").json()["reserved_bytes"] == 0


@pytest.mark.parametrize("size", [FILE_LIMIT - 1, FILE_LIMIT, FILE_LIMIT + 1])
def test_actual_streamed_500mb_boundaries_without_content_length(storage, size):
    client, files, _, _ = storage
    files.settings.storage_pool_bytes = FILE_LIMIT + 100
    declared = min(size, FILE_LIMIT)
    metadata = {"name": "boundary.bin", "size_bytes": declared}
    prefix = (
        b'--bound\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'
        + json.dumps(metadata).encode()
        + b'\r\n--bound\r\nContent-Disposition: form-data; name="file"; filename="ignored"\r\n\r\n'
    )

    async def body():
        yield prefix
        remaining = size
        while remaining:
            amount = min(65536, remaining)
            yield b"x" * amount
            remaining -= amount
        yield b"\r\n--bound--\r\n"

    async def perform():
        headers = {
            **csrf(client),
            "Content-Type": "multipart/form-data; boundary=bound",
            "Cookie": "; ".join(f"{cookie.name}={cookie.value}" for cookie in client.cookies.jar),
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=client.app), base_url="https://testserver"
        ) as transport:
            return await transport.post("/api/uploads", content=body(), headers=headers)

    response = asyncio.run(perform())
    assert response.status_code == (413 if size > FILE_LIMIT else 201), response.text
    if size <= FILE_LIMIT:
        assert response.json()["size_bytes"] == size
        checksum = hashlib.sha256()
        remaining = size
        while remaining:
            amount = min(65536, remaining)
            checksum.update(b"x" * amount)
            remaining -= amount
        assert response.json()["checksum_sha256"] == checksum.hexdigest()
    else:
        assert client.get("/api/storage").json()["reserved_bytes"] == 0


def test_quota_race_and_four_global_upload_limit(storage):
    client, files, _, _ = storage
    session, csrf_value = tokens(client)
    files.settings.storage_pool_bytes = 100

    def reserve(number):
        try:
            return files.reserve(
                session, csrf_value, UploadInput(name=f"race{number}", size_bytes=60), uuid.uuid4()
            )
        except AuthError as error:
            return error.status

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve, [1, 2]))
    assert 507 in results
    admitted = next(result for result in results if isinstance(result, dict))
    files.abandon(admitted)
    _, member_session, member_csrf = member(files.identity, invite(client)["token"])
    _, third_session, third_csrf = member(
        files.identity, invite(client)["token"], "third@example.net"
    )
    reservations = []
    for number, auth in enumerate(
        [(session, csrf_value)] * 2 + [(member_session, member_csrf)] * 2
    ):
        reservations.append(
            files.reserve(*auth, UploadInput(name=f"active{number}", size_bytes=1), uuid.uuid4())
        )
    with pytest.raises(AuthError) as error:
        files.reserve(
            third_session, third_csrf, UploadInput(name="fifth", size_bytes=1), uuid.uuid4()
        )
    assert error.value.status == 429
    for reserved in reservations:
        files.abandon(reserved)


def test_upload_revalidates_deactivation_and_deleted_destination(storage):
    client, files, _, _ = storage
    payload, session, csrf_value = member(files.identity, invite(client)["token"])
    item = receiver(
        client, files, {"name": "revoked-upload", "size_bytes": 3}, auth=(session, csrf_value)
    )
    item.feed(b"abc\r\n--testing--\r\n")
    response = client.patch(
        f"/api/admin/users/{payload['user']['id']}", json={"active": False}, headers=csrf(client)
    )
    assert response.status_code == 204
    with pytest.raises(AuthError) as error:
        item.finish()
    assert error.value.status == 401
    item.close()
    parent = folder(client)
    item = receiver(
        client, files, {"name": "removed-parent", "size_bytes": 3, "parent_id": parent["id"]}
    )
    item.feed(b"abc\r\n--testing--\r\n")
    trashed = mutate(client, parent, "trash").json()
    result = client.request(
        "DELETE",
        f"/api/trash/{parent['id']}",
        json={"expected_revision": trashed["revision"], "confirm": True},
        headers=csrf(client),
    )
    assert result.status_code == 200, result.text
    assert client.get("/api/storage").json()["reserved_bytes"] == 3
    with pytest.raises(AuthError):
        item.finish()
    item.close()
    assert client.get("/api/storage").json()["used_bytes"] == 0


def test_uncertain_commit_cleanup_never_deletes_published_content(storage, monkeypatch):
    client, files, _, _ = storage
    original = files.finish

    def uncertain(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("synthetic lost commit acknowledgement")

    with monkeypatch.context() as patch:
        patch.setattr(files, "finish", uncertain)
        assert upload(client, "uncertain", b"committed").status_code == 500
    items = [row for row in client.get("/api/items").json() if row["kind"] == "file"]
    assert len(items) == 1
    assert client.get(f"/api/items/{items[0]['id']}/download").content == b"committed"


def test_download_interruption_audit_and_open_handle_deletion(storage):
    from app.file_routes import Download

    client, files, _, _ = storage
    uploaded = upload(client, "stream", b"x" * 150000).json()
    session, _ = tokens(client)
    stream, item, actor = files.open_download(session, uuid.UUID(uploaded["id"]))
    response = Download(files, stream, item, actor, uuid.uuid4())

    async def exercise():
        async def receive():
            return {"type": "http.disconnect"}

        async def send(message):
            if message["type"] == "http.response.body":
                raise OSError("synthetic broken client connection")

        with pytest.raises(ClientDisconnect):
            await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)

    asyncio.run(exercise())
    assert stream.closed
    entry = next(
        event for event in client.get("/api/activity").json() if event["action"] == "download"
    )
    assert entry["details"]["server_stream"] == "interrupted"
    stream, item, _ = files.open_download(session, uuid.UUID(uploaded["id"]))
    trashed = mutate(client, uploaded, "trash").json()
    deletion = client.request(
        "DELETE",
        f"/api/trash/{uploaded['id']}",
        json={"expected_revision": trashed["revision"], "confirm": True},
        headers=csrf(client),
    )
    assert deletion.status_code == 200
    assert stream.read() == b"x" * 150000
    stream.close()
    files.reconcile()
    assert client.get(f"/api/admin/deletions/{deletion.json()['id']}").json()["state"] == "complete"


def test_bad_wire_claims_extra_parts_and_truncation_leave_no_content(storage):
    client, _, _, _ = storage
    headers = {
        **csrf(client),
        "Content-Type": "multipart/form-data; boundary=test-wire",
        "Content-Length": "1",
    }
    metadata = json.dumps({"name": "wire", "size_bytes": 3}).encode()
    start = b'--test-wire\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n' + metadata
    start += b'\r\n--test-wire\r\nContent-Disposition: form-data; name="file"; filename="x"\r\n\r\n'
    assert client.post("/api/uploads", content=start + b"abc", headers=headers).status_code == 422
    extra = (
        start + b'abc\r\n--test-wire\r\nContent-Disposition: form-data; name="extra"\r\n'
        b"\r\nx\r\n--test-wire--\r\n"
    )
    assert client.post("/api/uploads", content=extra, headers=headers).status_code == 422
    assert (
        client.post(
            "/api/uploads", content=start + b"abcd\r\n--test-wire--\r\n", headers=headers
        ).status_code
        == 413
    )
    result = client.post(
        "/api/uploads", content=start + b"abc\r\n--test-wire--\r\n", headers=headers
    )
    assert result.status_code == 201, result.text
    assert result.json()["size_bytes"] == 3
