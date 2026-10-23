"""Authenticated file API; byte transfers never use whole-file buffers."""

import asyncio
from contextlib import suppress
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from python_multipart.exceptions import MultipartParseError
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from app.file_models import (
    ROOT_ID,
    ActivityView,
    DeleteInput,
    DeletionView,
    FolderInput,
    ItemView,
    MoveInput,
    RevisionInput,
    StorageView,
    UploadInput,
    fail,
)
from app.file_upload import Upload
from app.identity_routes import context

router = APIRouter(prefix="/api", tags=["files"])


def service(request, mutation=False):
    _, session, csrf = context(request, mutation)
    return request.app.state.files, session, csrf


@router.get("/items", response_model=list[ItemView])
def browse(
    request: Request,
    parent_id: UUID = ROOT_ID,
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0, le=100000),
    q: str = Query("", max_length=255),
):
    files, session, _ = service(request)
    return files.browse(session, parent_id, limit, offset, q)


@router.get("/items/{identifier}", response_model=ItemView)
def item(identifier: UUID, request: Request):
    files, session, _ = service(request)
    return files.get(session, identifier)


@router.post("/folders", response_model=ItemView, status_code=201)
def folder(data: FolderInput, request: Request):
    files, session, csrf = service(request, True)
    return files.folder(session, csrf, data, request.state.request_id)


@router.patch("/items/{identifier}", response_model=ItemView)
def move(identifier: UUID, data: MoveInput, request: Request):
    files, session, csrf = service(request, True)
    return files.move(session, csrf, identifier, data, request.state.request_id)


@router.post("/items/{identifier}/trash", response_model=ItemView)
def trash(identifier: UUID, data: RevisionInput, request: Request):
    files, session, csrf = service(request, True)
    return files.trash(session, csrf, identifier, data, request.state.request_id)


@router.post("/items/{identifier}/restore", response_model=ItemView)
def restore(identifier: UUID, data: MoveInput, request: Request):
    files, session, csrf = service(request, True)
    return files.move(session, csrf, identifier, data, request.state.request_id, restore=True)


@router.get("/trash", response_model=list[ItemView])
def recycle_bin(
    request: Request, limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0, le=100000)
):
    files, session, _ = service(request)
    return files.trash_list(session, limit, offset)


@router.delete("/trash/{identifier}", response_model=DeletionView)
def delete(identifier: UUID, data: DeleteInput, request: Request):
    files, session, csrf = service(request, True)
    return files.delete(session, csrf, identifier, data, request.state.request_id)


@router.get("/admin/deletions/{identifier}", response_model=DeletionView)
def deletion(identifier: UUID, request: Request):
    files, session, _ = service(request)
    return files.job(session, identifier)


@router.get("/storage", response_model=StorageView)
def storage(request: Request):
    files, session, _ = service(request)
    return files.storage(session)


@router.get("/activity", response_model=list[ActivityView])
def activity(
    request: Request, limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0, le=100000)
):
    files, session, _ = service(request)
    return files.activity(session, limit, offset)


@router.post(
    "/uploads",
    response_model=ItemView,
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["metadata", "file"],
                        "properties": {
                            "metadata": UploadInput.model_json_schema(),
                            "file": {"type": "string", "format": "binary"},
                        },
                    },
                    "encoding": {"metadata": {"contentType": "application/json"}},
                }
            },
        },
        "description": "Metadata JSON first, then one file; maximum 500,000,000 file bytes.",
    },
)
async def upload(request: Request):
    files, session, csrf = service(request, True)

    def authorize():
        with files.transaction(session, csrf, mutation=True):
            pass
        files.reconcile()

    await run_in_threadpool(authorize)
    receiver = Upload(
        files, session, csrf, request.state.request_id, request.headers.get("content-type", "")
    )
    success = False
    try:
        iterator = request.stream().__aiter__()
        while True:
            try:
                chunk = await asyncio.wait_for(anext(iterator), timeout=30)
            except StopAsyncIteration:
                break
            for offset in range(0, len(chunk), 65536):
                await run_in_threadpool(receiver.feed, chunk[offset : offset + 65536])
        result = await run_in_threadpool(receiver.finish)
        success = True
        return result
    except (MultipartParseError, ClientDisconnect):
        fail("incomplete_upload", "The upload was interrupted or malformed", 422)
    except TimeoutError:
        fail("upload_timeout", "Upload timed out while waiting for data", 408)
    except OSError:
        fail("storage_unavailable", "Storage is temporarily unavailable", 503)
    finally:
        # Shield cleanup from disconnect cancellation. If the DB is unavailable, leave durable
        # intent for reconciliation; never guess whether an uncertain commit published bytes.
        import anyio

        with anyio.CancelScope(shield=True):
            with suppress(Exception):
                await run_in_threadpool(receiver.close, success)


class Download(StreamingResponse):
    def __init__(self, files, stream, item, actor, request_id):
        self.files, self.stream, self.item, self.actor, self.request_id = (
            files,
            stream,
            item,
            actor,
            request_id,
        )

        def chunks():
            while chunk := stream.read(65536):
                yield chunk

        super().__init__(
            chunks(),
            media_type="application/octet-stream",
            headers={
                "Content-Length": str(item["size_bytes"]),
                "Content-Disposition": "attachment; filename=\"download\"; filename*=UTF-8''"
                + quote(item["name"], safe=""),
                "Content-Security-Policy": "sandbox; default-src 'none'",
                "X-Content-Type-Options": "nosniff",
                "ETag": '"' + item["checksum_sha256"] + '"',
            },
        )

    async def __call__(self, scope, receive, send):
        complete = False

        async def observed(message):
            nonlocal complete
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                complete = True

        try:
            await super().__call__(scope, receive, observed)
        finally:
            self.stream.close()
            await run_in_threadpool(
                self.files.downloaded, self.actor, self.item, self.request_id, complete
            )


@router.get("/items/{identifier}/download", response_class=StreamingResponse)
def download(identifier: UUID, request: Request):
    files, session, _ = service(request)
    stream, item, actor = files.open_download(session, identifier)
    return Download(files, stream, item, actor, request.state.request_id)
