"""Stage 5 query/media boundaries exercised on the guarded PostgreSQL harness."""

import io
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image, PngImagePlugin
from sqlalchemy import text
from test_files import folder, identity, mutate, storage, upload  # noqa: F401
from test_identity import ORIGIN, PASSWORD, csrf, invite

from app.file_media import byte_range


@pytest.fixture
def manager_storage(request):
    return request.getfixturevalue("storage")


def png(size=(32, 24), color="blue", metadata=False):
    output = io.BytesIO()
    info = PngImagePlugin.PngInfo()
    if metadata:
        info.add_text("private", "untrusted metadata")
    Image.new("RGB", size, color).save(output, format="PNG", pnginfo=info)
    return output.getvalue()


def icon(client, item, payload=None):
    headers = {key: value for key, value in csrf(client).items() if key != "Content-Type"}
    return client.put(
        f"/api/items/{item['id']}/icon?expected_revision={item['revision']}",
        content=png(metadata=True) if payload is None else payload,
        headers=headers,
    )


def test_browse_filters_sort_before_pagination_and_live_ancestors(manager_storage):
    client, _, _, admin = manager_storage
    parent = folder(client)
    rows = [
        upload(client, name, data, parent_id=parent["id"]).json()
        for name, data in [("a.pdf", b"abc"), ("b.png", b"12345"), ("c.pdf", b"1")]
    ]
    root = f"/api/browse?parent_id={parent['id']}"
    result = client.get(root + "&category=pdf&sort=size&direction=desc&limit=1&offset=1")
    assert result.status_code == 200
    assert [item["id"] for item in result.json()] == [rows[2]["id"]]
    assert len(client.get(root + f"&uploader={admin['id']}").json()) == 3
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert client.get(root, params={"after": future}).json() == []
    assert client.get(root + "&category=bogus").status_code == 422
    assert client.get(root + "&sort=name;DROP TABLE items").status_code == 422
    assert (
        client.get(root, params={"after": future, "before": "2020-01-01T00:00:00Z"}).status_code
        == 422
    )
    assert client.get("/api/browse?scope=all&q=a.pdf").json()[0]["id"] == rows[0]["id"]
    path = client.get(f"/api/folders/{parent['id']}/breadcrumbs").json()
    assert path[-1]["id"] == parent["id"]
    assert mutate(client, parent, "trash").status_code == 200
    assert client.get("/api/browse?scope=all&q=a.pdf").json() == []


def test_private_media_icons_metadata_revision_and_content_integrity(manager_storage):
    client, _, _, _ = manager_storage
    original = b"original file bytes\x00\xff"
    item = upload(client, payload=original).json()
    changed = icon(client, item)
    assert changed.status_code == 200, changed.text
    assert changed.json()["has_icon"] is True
    assert changed.json()["revision"] == item["revision"] + 1
    response = client.get(f"/api/items/{item['id']}/icon")
    assert response.headers["content-type"] == "image/png"
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.size == (32, 24)
        assert "private" not in image.info
    assert icon(client, item).status_code == 409
    assert client.get(f"/api/items/{item['id']}/download").content == original
    updated = changed.json()
    assert (
        client.request(
            "DELETE",
            f"/api/items/{item['id']}/icon",
            json={"expected_revision": updated["revision"]},
            headers=csrf(client),
        ).status_code
        == 200
    )
    assert client.get(f"/api/items/{item['id']}/icon").status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        b"<html>bad</html>",
        b"\x89PNG\r\n\x1a\ntruncated",
        b"x" * 2_000_001,
    ],
    ids=["svg", "html", "truncated-png", "oversize"],
)
def test_malicious_or_oversized_icon_never_publishes(manager_storage, payload):
    client, _, engine, _ = manager_storage
    item = upload(client).json()
    assert icon(client, item, payload).status_code in {413, 422}
    assert client.get(f"/api/items/{item['id']}").json()["has_icon"] is False
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM blobs")) == 1


def test_icon_pixel_bound_and_preview_safe_reencoding(manager_storage):
    client, _, _, _ = manager_storage
    item = upload(client, "image.png", png(metadata=True)).json()
    assert icon(client, item, png((2100, 2000))).status_code == 422
    response = client.get(f"/api/items/{item['id']}/preview")
    assert response.status_code == 200
    assert response.headers["content-security-policy"].startswith("sandbox")
    with Image.open(io.BytesIO(response.content)) as image:
        assert "private" not in image.info
    fake = upload(client, "spoof.png", b"<script>alert(1)</script>").json()
    assert client.get(f"/api/items/{fake['id']}/preview").status_code == 422
    svg = upload(client, "drawing.svg", b"<svg/>").json()
    assert client.get(f"/api/items/{svg['id']}/preview").status_code == 415


def test_icon_retirement_failure_charged_and_retry_safe(manager_storage, monkeypatch):
    client, files, engine, _ = manager_storage
    item = icon(client, upload(client).json()).json()
    before = client.get("/api/storage").json()["used_bytes"]
    discard = files.store.discard
    monkeypatch.setattr(
        files.store, "discard", lambda key: (_ for _ in ()).throw(OSError("test locked file"))
    )
    response = client.request(
        "DELETE",
        f"/api/items/{item['id']}/icon",
        json={"expected_revision": item["revision"]},
        headers=csrf(client),
    )
    assert response.status_code == 200
    assert client.get("/api/storage").json()["used_bytes"] == before
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM media_cleanup")) == 1
    monkeypatch.setattr(files.store, "discard", discard)
    files.reconcile()
    assert client.get("/api/storage").json()["used_bytes"] < before
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM media_cleanup")) == 0


def test_preview_ranges_spoofing_trash_and_member_admin_isolation(manager_storage):
    client, _, _, _ = manager_storage
    payload = b"%PDF-1.7\n" + b"0" * 120
    item = upload(client, "document.pdf", payload).json()
    url = f"/api/items/{item['id']}/preview"
    response = client.get(url, headers={"Range": "bytes=2-8"})
    assert response.status_code == 206 and response.content == payload[2:9]
    assert response.headers["content-range"] == f"bytes 2-8/{len(payload)}"
    assert client.get(url, headers={"Range": "bytes=-4"}).content == payload[-4:]
    assert client.get(url, headers={"Range": "bytes=999-"}).status_code == 416
    assert client.get(url, headers={"Range": "bytes=0-1,4-5"}).status_code == 416
    invitation = invite(client)
    response = client.post(
        "/api/auth/invitations/redeem",
        json={"email": "member@example.net", "password": PASSWORD, "token": invitation["token"]},
        headers=ORIGIN,
    )
    assert response.status_code == 201
    assert client.get(url).status_code == 200
    assert client.get("/api/admin/activity").status_code == 403
    assert client.get("/api/admin/storage").status_code == 403
    assert client.get("/api/admin/trash").status_code == 403
    assert client.get("/api/people").status_code == 200
    assert all(
        event["action"] not in {"login", "invitation_create"}
        for event in client.get("/api/events").json()
    )
    current = client.get(f"/api/items/{item['id']}").json()
    assert mutate(client, current, "trash").status_code == 200
    assert client.get(url).status_code == 404
    client.cookies.clear()
    assert client.get(url).status_code == 401
    assert (
        client.put(
            f"/api/items/{item['id']}/icon?expected_revision=1", content=png(), headers=ORIGIN
        ).status_code
        == 401
    )


def test_icon_csrf_and_oversize_dishonest_wire(manager_storage):
    client, _, _, _ = manager_storage
    item = upload(client).json()
    assert (
        client.put(
            f"/api/items/{item['id']}/icon?expected_revision=1",
            content=png(),
            headers={"Origin": ORIGIN["Origin"]},
        ).status_code
        == 403
    )
    assert icon(client, item, b"x" * 2_000_001).status_code == 413


def test_range_parser_edges():
    assert byte_range("bytes=1-", 5) == (1, 4, 206)
    assert byte_range("bytes=-100", 5) == (0, 4, 206)
    assert byte_range("bytes=-0", 5) is None
    assert byte_range("bytes=3-1", 5) is None
    assert byte_range(None, 5) == (0, 4, 200)
    assert byte_range("bytes=" + "9" * 5000 + "-", 5) is None


def test_collision_probe_uses_server_unicode_casefold_and_auth(manager_storage):
    client, _, _, _ = manager_storage
    item = upload(client, "Straße.txt").json()
    result = client.get("/api/collisions", params={"name": "STRASSE.txt"})
    assert result.status_code == 200 and result.json()["id"] == item["id"]
    assert client.get("/api/collisions", params={"name": "absent.txt"}).json() is None
    assert client.get("/api/collisions", params={"name": "../bad"}).status_code == 422
    client.cookies.clear()
    assert client.get("/api/collisions", params={"name": "STRASSE.txt"}).status_code == 401


def test_admin_pending_deletion_retry_preserves_confirmed_intent(manager_storage, monkeypatch):
    client, files, _, _ = manager_storage
    item = mutate(client, upload(client).json(), "trash").json()
    discard = files.store.discard
    monkeypatch.setattr(
        files.store, "discard", lambda key: (_ for _ in ()).throw(OSError("locked"))
    )
    job = client.request(
        "DELETE",
        f"/api/trash/{item['id']}",
        json={"expected_revision": item["revision"], "confirm": True},
        headers=csrf(client),
    ).json()
    assert job["state"] == "pending"
    assert client.get("/api/admin/deletions").json()[0]["id"] == job["id"]
    retry = f"/api/admin/deletions/{job['id']}/retry"
    assert client.post(retry, json={}, headers=ORIGIN).status_code == 403
    assert client.post(retry, json={"confirm": False}, headers=csrf(client)).status_code == 422
    invitation = invite(client)
    assert (
        client.post(
            "/api/auth/invitations/redeem",
            json={
                "email": "member@example.net",
                "password": PASSWORD,
                "token": invitation["token"],
            },
            headers=ORIGIN,
        ).status_code
        == 201
    )
    assert client.get("/api/admin/deletions").status_code == 403
    assert client.post(retry, json={}, headers=csrf(client)).status_code == 403
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": PASSWORD},
            headers=ORIGIN,
        ).status_code
        == 200
    )
    monkeypatch.setattr(files.store, "discard", discard)
    assert client.post(retry, json={}, headers=csrf(client)).json()["state"] == "complete"
    assert client.get("/api/admin/deletions").json() == []
    assert client.post(retry, json={}, headers=csrf(client)).json()["state"] == "complete"
