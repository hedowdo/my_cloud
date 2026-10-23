"""Shared, folder-scoped placement; position revisions never change file revisions."""

import math
from uuid import UUID

from fastapi import Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.file_models import fail
from app.file_routes import router, service
from app.identity_security import StrictInput


class PositionInput(StrictInput):
    parent_id: UUID
    expected_revision: int = Field(ge=0, strict=True)
    expected_item_revision: int = Field(ge=1, strict=True)
    x: float = Field(ge=-1_000_000, le=1_000_000, allow_inf_nan=False, strict=True)
    y: float = Field(ge=-1_000_000, le=1_000_000, allow_inf_nan=False, strict=True)


class PositionView(BaseModel):
    item_id: UUID
    x: float
    y: float
    revision: int


class PlacementInput(StrictInput):
    item_ids: list[UUID] = Field(max_length=500)


@router.post("/folders/{identifier}/positions/initialize", response_model=list[PositionView])
def initialize(identifier: UUID, data: PlacementInput, request: Request):
    files, session, csrf = service(request, True)
    with files.transaction(session, csrf, mutation=True) as (connection, actor):
        files.directory(connection, identifier)
        occupied = list(
            connection.execute(
                text("""SELECT p.x,p.y FROM positions p JOIN items i ON i.id=p.item_id
            WHERE i.parent_id=:parent AND i.trashed_at IS NULL"""),
                {"parent": identifier},
            ).mappings()
        )
        missing = connection.execute(
            text("""SELECT i.id FROM items i LEFT JOIN positions p ON p.item_id=i.id
            WHERE i.parent_id=:parent AND i.trashed_at IS NULL
            AND i.deletion_job_id IS NULL AND i.id=ANY(:ids) AND p.item_id IS NULL
            ORDER BY i.created_at,i.id"""),
            {"parent": identifier, "ids": data.item_ids},
        ).mappings()
        candidate = 0
        for item in missing:
            while True:
                # Golden-angle spiral: deterministic, separated from core and saved nodes.
                angle = candidate * 2.399963229728653
                radius = 240 + 95 * math.sqrt(candidate)
                candidate += 1
                x, y = round(math.cos(angle) * radius, 2), round(math.sin(angle) * radius, 2)
                if all((x - p["x"]) ** 2 + (y - p["y"]) ** 2 >= 125**2 for p in occupied):
                    break
            connection.execute(
                text("""INSERT INTO positions (item_id,x,y,updated_by)
                VALUES (:id,:x,:y,:actor)"""),
                {"id": item["id"], "x": x, "y": y, "actor": actor["id"]},
            )
            occupied.append({"x": x, "y": y})
        return list(
            connection.execute(
                text("""SELECT p.item_id,p.x,p.y,p.revision FROM positions p
            JOIN items i ON i.id=p.item_id
            WHERE i.parent_id=:parent AND i.id=ANY(:ids) AND i.trashed_at IS NULL
            AND i.deletion_job_id IS NULL ORDER BY i.id"""),
                {"parent": identifier, "ids": data.item_ids},
            ).mappings()
        )


@router.get("/folders/{identifier}/positions", response_model=list[PositionView])
def positions(identifier: UUID, request: Request):
    files, session, _ = service(request)
    with files.transaction(session) as (connection, _):
        files.directory(connection, identifier)
        # Offset pagination of browse remains the full-directory fallback. This route
        # only returns existing positions, bounded to match the canvas metadata cap.
        return list(
            connection.execute(
                text("""SELECT p.item_id,p.x,p.y,p.revision FROM positions p
                JOIN items i ON i.id=p.item_id WHERE i.parent_id=:parent
                AND i.trashed_at IS NULL AND i.deletion_job_id IS NULL
                ORDER BY i.id LIMIT 10000"""),
                {"parent": identifier},
            ).mappings()
        )


@router.patch("/items/{identifier}/position", response_model=PositionView)
def position(identifier: UUID, data: PositionInput, request: Request):
    files, session, csrf = service(request, True)
    with files.transaction(session, csrf, mutation=True) as (connection, actor):
        item = files.live(connection, identifier)
        if item["parent_id"] != data.parent_id:
            fail("position_parent_conflict", "This item moved. Reopen its folder", 409)
        files.revision(item, data.expected_item_revision)
        current = connection.execute(
            text("SELECT revision FROM positions WHERE item_id=:id"), {"id": identifier}
        ).scalar_one_or_none()
        if (current or 0) != data.expected_revision:
            fail("position_conflict", "Someone moved this node. Review its position and retry", 409)
        return (
            connection.execute(
                text("""INSERT INTO positions (item_id,x,y,updated_by)
            VALUES (:id,:x,:y,:actor) ON CONFLICT (item_id) DO UPDATE
            SET x=EXCLUDED.x,y=EXCLUDED.y,revision=positions.revision+1,
            updated_by=EXCLUDED.updated_by,updated_at=now()
            RETURNING item_id,x,y,revision"""),
                {"id": identifier, "x": data.x, "y": data.y, "actor": actor["id"]},
            )
            .mappings()
            .one()
        )
