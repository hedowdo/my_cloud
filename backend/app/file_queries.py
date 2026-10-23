"""Bounded shared-space queries; filtering happens before stable pagination."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from sqlalchemy import text

from app.file_models import (
    FILE_ACTIONS,
    ROOT_ID,
    ActivityView,
    DeletionView,
    ItemView,
    StorageView,
    clean_name,
    fail,
)
from app.file_routes import router, service
from app.file_service import COLUMNS
from app.identity_security import StrictInput

KINDS = {
    "image": r"\.(png|jpe?g|webp|gif|bmp|tiff?)$",
    "pdf": r"\.pdf$",
    "video": r"\.(mp4|webm|mov|mkv|avi)$",
    "document": r"\.(txt|md|csv|docx?|xlsx?|pptx?|odt|rtf)$",
    "archive": r"\.(zip|gz|tar|7z|rar)$",
}


def dates(after, before):
    if any(value is not None and value.utcoffset() is None for value in (after, before)):
        fail("invalid_dates", "Use dates with an explicit timezone", 422)
    if after and before and after > before:
        fail("invalid_dates", "Start date must precede end date", 422)


@router.get("/collisions", response_model=ItemView | None)
def collision(request: Request, name: str = Query(max_length=255), parent_id: UUID = ROOT_ID):
    files, session, _ = service(request)
    try:
        name = clean_name(name)
    except ValueError:
        fail("invalid_name", "Choose a valid file name", 422)
    with files.transaction(session) as (connection, _):
        files.directory(connection, parent_id)
        _, other = files.collision(connection, parent_id, name, "replace")
        return files.view(files.live(connection, other["id"])) if other else None


@router.get("/browse", response_model=list[ItemView])
def browse_filtered(
    request: Request,
    parent_id: UUID = ROOT_ID,
    q: str = Query("", max_length=255),
    category: Literal[
        "all", "folder", "image", "pdf", "video", "document", "archive", "other"
    ] = "all",
    uploader: UUID | None = None,
    after: datetime | None = None,
    before: datetime | None = None,
    sort: Literal["name", "size", "date"] = "name",
    direction: Literal["asc", "desc"] = "asc",
    scope: Literal["folder", "all"] = "folder",
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0, le=100000),
):
    files, session, _ = service(request)
    dates(after, before)
    clauses = ["strpos(i.name_key,:query)>0"]
    params = {"parent": parent_id, "query": q.casefold(), "limit": limit, "offset": offset}
    if scope == "folder":
        clauses.append("i.parent_id=:parent")
    if category == "folder":
        clauses.append("i.kind='folder'")
    elif category in KINDS:
        clauses.append("i.kind='file' AND lower(i.name) ~ :pattern")
        params["pattern"] = KINDS[category]
    elif category == "other":
        clauses.append("i.kind='file' AND NOT (lower(i.name) ~ :pattern)")
        params["pattern"] = "|".join(KINDS.values())
    for key, value, clause in [
        ("uploader", uploader, "i.uploader_id=:uploader"),
        ("after", after, "i.created_at>=:after"),
        ("before", before, "i.created_at<=:before"),
    ]:
        if value is not None:
            clauses.append(clause)
            params[key] = value
    field = {"name": "i.name_key", "size": "coalesce(b.size_bytes,-1)", "date": "i.created_at"}[
        sort
    ]
    # ORDER expressions come exclusively from closed enum maps, never raw user input.
    sql = (
        """WITH RECURSIVE visible AS (
        SELECT id,0 AS depth FROM items WHERE id='00000000-0000-0000-0000-000000000001'
        UNION ALL SELECT child.id,v.depth+1 FROM items child JOIN visible v ON child.parent_id=v.id
        WHERE child.trashed_at IS NULL AND child.deletion_job_id IS NULL AND v.depth<64)
        """
        + COLUMNS
        + " JOIN visible v ON v.id=i.id WHERE i.id<>:root AND "
    )
    params["root"] = ROOT_ID
    sql += " AND ".join(clauses) + f" ORDER BY {field} {direction},i.id LIMIT :limit OFFSET :offset"
    with files.transaction(session) as (connection, _):
        files.directory(connection, parent_id)
        return [files.view(row) for row in connection.execute(text(sql), params).mappings()]


@router.get("/people")
def people(request: Request):
    files, session, _ = service(request)
    with files.transaction(session) as (connection, _):
        return [
            dict(row)
            for row in connection.execute(
                text("SELECT id,email FROM users ORDER BY email_key,id LIMIT 5")
            ).mappings()
        ]


@router.get("/folders/{identifier}/breadcrumbs", response_model=list[ItemView])
def breadcrumbs(identifier: UUID, request: Request):
    files, session, _ = service(request)
    with files.transaction(session) as (connection, _):
        return [files.view(row) for row in reversed(files.directory(connection, identifier))]


@router.get("/events", response_model=list[ActivityView])
@router.get("/admin/activity", response_model=list[ActivityView])
def events(
    request: Request,
    q: str = Query("", max_length=255),
    action: str = Query("", max_length=40),
    actor: UUID | None = None,
    after: datetime | None = None,
    before: datetime | None = None,
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0, le=100000),
):
    files, session, _ = service(request)
    admin = request.url.path.startswith("/api/admin/")
    clauses, params = (
        ["strpos(lower(target_name),:q)>0"],
        {"q": q.lower(), "limit": limit, "offset": offset},
    )
    if not admin:
        clauses.append("action=ANY(:actions)")
        params["actions"] = list(FILE_ACTIONS)
    for key, value, clause in [
        ("action", action, "action=:action"),
        ("actor", actor, "actor_id=:actor"),
        ("after", after, "occurred_at>=:after"),
        ("before", before, "occurred_at<=:before"),
    ]:
        if value:
            clauses.append(clause)
            params[key] = value
    dates(after, before)
    with files.transaction(session, admin=admin) as (connection, _):
        # Shared history includes bounded file details. Security event internals stay private.
        return [
            dict(row)
            for row in connection.execute(
                text(
                    "SELECT id,actor_id,action,target_id,target_name,occurred_at,"
                    "'{}'::jsonb AS details FROM activity WHERE "
                    + " AND ".join(clauses)
                    + " ORDER BY occurred_at DESC,id LIMIT :limit OFFSET :offset"
                ),
                params,
            ).mappings()
        ]


@router.get("/admin/storage", response_model=StorageView)
def admin_storage(request: Request):
    files, session, _ = service(request)
    with files.transaction(session, admin=True):
        pass
    return files.storage(session)


@router.get("/admin/trash", response_model=list[ItemView])
def admin_trash(
    request: Request, limit: int = Query(24, ge=1, le=100), offset: int = Query(0, ge=0, le=100000)
):
    files, session, _ = service(request)
    with files.transaction(session, admin=True):
        pass
    return files.trash_list(session, limit, offset)


@router.get("/admin/deletions", response_model=list[DeletionView])
def pending_deletions(
    request: Request, limit: int = Query(24, ge=1, le=100), offset: int = Query(0, ge=0, le=100000)
):
    files, session, _ = service(request)
    with files.transaction(session, admin=True) as (connection, _):
        return [
            dict(row)
            for row in connection.execute(
                text(
                    "SELECT id,target_id,state,last_error,item_count,created_at,completed_at "
                    "FROM deletion_jobs WHERE state='pending' ORDER BY created_at,id "
                    "LIMIT :limit OFFSET :offset"
                ),
                {"limit": limit, "offset": offset},
            ).mappings()
        ]


class RetryDeletion(StrictInput):
    pass


@router.post("/admin/deletions/{identifier}/retry", response_model=DeletionView)
def retry_deletion(identifier: UUID, data: RetryDeletion, request: Request):
    files, session, csrf = service(request, True)
    with files.transaction(session, csrf, mutation=True, admin=True) as (connection, _):
        if not connection.scalar(
            text("SELECT 1 FROM deletion_jobs WHERE id=:id"), {"id": identifier}
        ):
            fail()
    files.process_deletion(identifier)
    return files.job(session, identifier)
