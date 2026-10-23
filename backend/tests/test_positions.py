"""Shared placement security, persistence and races on the disposable DB harness."""

import json
import math
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_files import folder, identity, mutate, storage  # noqa: F401
from test_identity import ORIGIN, PASSWORD, csrf, invite, member

from app.file_models import ROOT_ID


@pytest.fixture
def positioned(request):
    return request.getfixturevalue("storage")


def put(client, item, revision=0, x=300, y=-200, parent=None):
    return client.patch(
        f"/api/items/{item['id']}/position",
        json={
            "parent_id": parent or item["parent_id"],
            "expected_revision": revision,
            "expected_item_revision": item["revision"],
            "x": x,
            "y": y,
        },
        headers=csrf(client),
    )


def initialize(client, items, parent=str(ROOT_ID)):
    return client.post(
        f"/api/folders/{parent}/positions/initialize",
        json={"item_ids": [item["id"] for item in items]},
        headers=csrf(client),
    )


def test_shared_position_revision_and_parent_conflicts(positioned):
    client, _, _, _ = positioned
    identity_service = client.app.state.identity
    item = folder(client)
    token = invite(client)["token"]
    member(identity_service, token)
    with TestClient(client.app, base_url="https://testserver") as other:
        assert (
            other.post(
                "/api/auth/login",
                json={"email": "member@example.net", "password": PASSWORD},
                headers=ORIGIN,
            ).status_code
            == 200
        )
        row = put(client, item).json()
        assert row["revision"] == 1
        assert other.get(f"/api/folders/{ROOT_ID}/positions").json() == [row]
        assert client.get(f"/api/items/{item['id']}").json()["revision"] == item["revision"]
        assert put(other, item).status_code == 409
        row2 = put(other, item, 1, x=0, y=0)
        assert row2.status_code == 200 and row2.json()["revision"] == 2
        assert put(client, item, 1).status_code == 409
        destination = folder(client, "destination")
        moved = client.patch(
            f"/api/items/{item['id']}",
            json={"expected_revision": item["revision"], "parent_id": destination["id"]},
            headers=csrf(client),
        )
        assert moved.status_code == 200
        assert put(client, item, 2).status_code == 409
        assert client.get(f"/api/folders/{ROOT_ID}/positions").json() == []
        assert put(client, moved.json()).status_code == 200
        assert mutate(client, destination, "trash").status_code == 200
        assert put(other, moved.json(), 1).status_code == 404
        assert client.get(f"/api/folders/{destination['id']}/positions").status_code == 404


def test_initial_placement_persisted_separated_idempotent_and_no_overwrite(positioned):
    client, _, engine, admin = positioned
    items = [
        {"id": str(uuid.uuid4()), "parent_id": str(ROOT_ID), "revision": 1, "name": f"node-{i}"}
        for i in range(500)
    ]
    with engine.begin() as connection:
        connection.execute(
            text("""INSERT INTO items (id,parent_id,kind,name,name_key,uploader_id)
        VALUES (:id,:parent_id,'folder',:name,:name,:uploader)"""),
            [{**item, "uploader": admin["id"]} for item in items],
        )
    assert put(client, items[0], x=240, y=0).status_code == 200
    for batch in [items[:250], items[250:]]:
        response = initialize(client, batch)
        assert response.status_code == 200, response.text
        assert initialize(client, list(reversed(batch))).json() == response.json()
    rows = client.get(f"/api/folders/{ROOT_ID}/positions").json()
    assert len(rows) == 500
    for i, a in enumerate(rows):
        assert math.hypot(a["x"], a["y"]) >= 200
        for b in rows[i + 1 :]:
            assert math.hypot(a["x"] - b["x"], a["y"] - b["y"]) >= 124.99
    extra = folder(client, "extra")
    assert initialize(client, [extra]).status_code == 200
    combined = client.get(f"/api/folders/{ROOT_ID}/positions").json()
    assert all(row in combined for row in rows)
    assert len(combined) == 501


def test_first_and_subsequent_concurrent_position_writes(positioned):
    client, _, _, _ = positioned
    item = folder(client)
    for revision in [0, 1]:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda x, revision=revision: put(client, item, revision, x=x).status_code,
                    [200, 400],
                )
            )
        assert sorted(results) == [200, 409]


def test_drag_cannot_survive_move_away_and_back_or_file_revision_change(positioned):
    client, _, _, _ = positioned
    item = folder(client, "node")
    destination = folder(client, "destination")
    assert put(client, item).status_code == 200
    moved = client.patch(
        f"/api/items/{item['id']}",
        json={"expected_revision": item["revision"], "parent_id": destination["id"]},
        headers=csrf(client),
    ).json()
    returned = client.patch(
        f"/api/items/{item['id']}",
        json={"expected_revision": moved["revision"], "parent_id": str(ROOT_ID)},
        headers=csrf(client),
    ).json()
    assert put(client, returned).status_code == 200
    assert put(client, item, 1).status_code == 409
    renamed = client.patch(
        f"/api/items/{item['id']}",
        json={"expected_revision": returned["revision"], "name": "renamed"},
        headers=csrf(client),
    ).json()
    assert put(client, returned, 1).status_code == 409
    assert put(client, renamed, 1).status_code == 200


def test_position_auth_csrf_strict_bounds_and_live_scope(positioned):
    client, _, _, _ = positioned
    item = folder(client)
    endpoint = f"/api/items/{item['id']}/position"
    body = {
        "parent_id": item["parent_id"],
        "expected_revision": 0,
        "expected_item_revision": item["revision"],
        "x": 0,
        "y": 0,
    }
    assert client.patch(endpoint, json=body, headers=ORIGIN).status_code == 403
    for field, value in [
        ("x", 1_000_001),
        ("y", -1_000_001),
        ("x", "Infinity"),
        ("x", "NaN"),
        ("x", True),
        ("expected_revision", -1),
        ("expected_revision", True),
        ("extra", 1),
    ]:
        assert (
            client.patch(endpoint, json={**body, field: value}, headers=csrf(client)).status_code
            == 422
        )
    assert put(client, item, x=-1_000_000, y=1_000_000).status_code == 200
    with TestClient(client.app, base_url="https://testserver") as anonymous:
        assert anonymous.get(f"/api/folders/{ROOT_ID}/positions").status_code == 401
        assert anonymous.patch(endpoint, json=body, headers=ORIGIN).status_code == 401
    assert initialize(client, [item] * 501).status_code == 413
    assert (
        client.post(
            f"/api/folders/{ROOT_ID}/positions/initialize",
            json={"item_ids": [item["id"]]},
            headers=ORIGIN,
        ).status_code
        == 403
    )
    assert mutate(client, item, "trash").status_code == 200
    assert put(client, item, 1).status_code == 404
    assert initialize(client, [item]).json() == []


def test_initialization_metadata_boundary_json_and_actual_byte_limits(positioned):
    client, _, _, _ = positioned
    item = folder(client)
    endpoint = f"/api/folders/{ROOT_ID}/positions/initialize"
    body = json.dumps({"item_ids": [item["id"]]})
    assert (
        client.post(endpoint, content=body + " " * 20000, headers=csrf(client)).status_code == 413
    )
    headers = {**csrf(client), "Content-Type": "text/plain"}
    assert client.post(endpoint, content=body, headers=headers).status_code == 415
    assert initialize(client, [item]).status_code == 200
