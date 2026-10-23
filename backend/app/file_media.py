"""Private allowlisted previews and bounded, metadata-free raster icons."""

import asyncio
import hashlib
import io
import os
import re
import threading
import uuid
from contextlib import suppress

from fastapi import Query, Request
from fastapi.responses import Response, StreamingResponse
from PIL import Image, ImageOps, PngImagePlugin, UnidentifiedImageError
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from app.file_models import ItemView, RevisionInput, UploadInput, fail
from app.file_routes import router, service
from app.file_service import advisory_key

ICON_LIMIT = 2_000_000
IMAGE_LIMIT = 10_000_000
PDF_LIMIT = 25_000_000
IMAGE_WORK = threading.BoundedSemaphore(2)
Image.MAX_IMAGE_PIXELS = 16_000_000
PngImagePlugin.MAX_TEXT_CHUNK = 64 * 1024
PngImagePlugin.MAX_TEXT_MEMORY = 256 * 1024
SAFE_HEADERS = {
    "Content-Security-Policy": "sandbox; default-src 'none'",
    "X-Content-Type-Options": "nosniff",
}


class PreviewStream(StreamingResponse):
    def __init__(self, descriptor, content, **kwargs):
        self.descriptor = descriptor
        super().__init__(content, **kwargs)

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            # Also closes if a disconnect occurs before iteration starts.
            self.descriptor.close()


def raster(data, *, icon=False):
    if len(data) > (ICON_LIMIT if icon else IMAGE_LIMIT):
        fail("image_too_large", "Image is too large for this preview", 413)
    if not IMAGE_WORK.acquire(blocking=False):
        fail("media_busy", "Another image is being prepared. Please retry", 429)
    try:
        try:
            with Image.open(io.BytesIO(data), formats=["PNG", "JPEG", "WEBP"]) as image:
                pixels = image.width * image.height
                if pixels > (4_000_000 if icon else 16_000_000) or pixels < 1:
                    fail("image_dimensions", "Choose a smaller image", 422)
                image.seek(0)
                image.load()
                oriented = ImageOps.exif_transpose(image).convert("RGBA")
                oriented.thumbnail((256, 256) if icon else (2048, 2048))
                # Fresh pixels carry no EXIF/XMP/ICC/text/animation from the upload.
                clean = Image.new("RGBA", oriented.size)
                clean.paste(oriented)
                result = io.BytesIO()
                clean.save(result, format="PNG")
                return result.getvalue()
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            SyntaxError,
            Image.DecompressionBombError,
        ):
            fail("unsupported_image", "Use a valid PNG, JPEG or WebP image", 422)
    finally:
        IMAGE_WORK.release()


def retire(connection, blob):
    if blob and not connection.scalar(
        text("SELECT 1 FROM items WHERE blob_id=:id OR icon_blob_id=:id LIMIT 1"), {"id": blob}
    ):
        connection.execute(text("UPDATE blobs SET state='deleting' WHERE id=:id"), {"id": blob})
        connection.execute(
            text("INSERT INTO media_cleanup(blob_id) VALUES (:id) ON CONFLICT DO NOTHING"),
            {"id": blob},
        )


def clean_retired_icons(files):
    with files.engine.begin() as connection:
        from app.identity_service import lock

        lock(connection)
        for blob in connection.execute(
            text("""SELECT b.id,b.storage_key FROM media_cleanup c
            JOIN blobs b ON b.id=c.blob_id WHERE NOT EXISTS
            (SELECT 1 FROM items WHERE blob_id=b.id OR icon_blob_id=b.id) LIMIT 100""")
        ).mappings():
            try:
                files.store.discard(blob["storage_key"])
            except OSError:
                continue
            connection.execute(text("DELETE FROM blobs WHERE id=:id"), {"id": blob["id"]})


def set_icon(files, session, csrf, identifier, revision, payload, request_id):
    with files.transaction(session, csrf, mutation=True) as (connection, _):
        row = files.live(connection, identifier)
        files.revision(row, revision)
        if row["kind"] != "file":
            fail("file_required", "Choose a file for the custom icon", 422)
        parent = row["parent_id"]
    data = raster(payload, icon=True)
    intent = UploadInput(
        name=f"icon-{uuid.uuid4().hex}.png", parent_id=parent, size_bytes=len(data)
    )
    reservation = files.reserve(session, csrf, intent, request_id)
    lease = None
    try:
        lease = files.engine.connect()
        lease.execute(
            text("SELECT pg_advisory_lock(:key)"), {"key": advisory_key(reservation["blob_id"])}
        )
        lease.commit()
        with files.store.create(reservation["key"]) as stream, files.engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(735104)"))
            if files.store.free() - len(data) < files.settings.storage_reserve_bytes:
                fail("disk_reserve", "Insufficient safe disk space", 507)
            if stream.write(data) != len(data):
                raise OSError("Short icon write")
            stream.flush()
            os.fsync(stream.fileno())
        with files.transaction(session, csrf, mutation=True) as (connection, actor):
            row = files.live(connection, identifier)
            files.revision(row, revision)
            files.store.publish(reservation["key"])
            connection.execute(
                text("""UPDATE blobs SET state='durable',size_bytes=:size,
                checksum_sha256=:hash,media_type='image/png' WHERE id=:id"""),
                {
                    "id": reservation["blob_id"],
                    "size": len(data),
                    "hash": hashlib.sha256(data).hexdigest(),
                },
            )
            connection.execute(
                text("""UPDATE items SET icon_blob_id=:blob,revision=revision+1,
                updated_at=now() WHERE id=:id"""),
                {"id": identifier, "blob": reservation["blob_id"]},
            )
            connection.execute(
                text(
                    "UPDATE upload_reservations SET state='complete',received_bytes=:size "
                    "WHERE id=:id"
                ),
                {"id": reservation["id"], "size": len(data)},
            )
            retire(connection, row["icon_blob_id"])
            result = files.view(files.raw(connection, identifier))
            files.audit(connection, actor["id"], "icon_update", result, request_id)
        with suppress(Exception):
            clean_retired_icons(files)
        return result
    finally:
        # A fresh reference check also protects the icon after an uncertain successful commit.
        with suppress(Exception):
            files.abandon(reservation)
        if lease:
            lease.execute(
                text("SELECT pg_advisory_unlock(:key)"),
                {"key": advisory_key(reservation["blob_id"])},
            )
            lease.commit()
            lease.close()


@router.put("/items/{identifier}/icon", response_model=ItemView)
async def put_icon(identifier: uuid.UUID, request: Request, expected_revision: int = Query(ge=1)):
    files, session, csrf = service(request, True)

    def authorize():
        with files.transaction(session, csrf, mutation=True) as (connection, _):
            files.revision(files.live(connection, identifier), expected_revision)

    await run_in_threadpool(authorize)
    data = bytearray()
    iterator = request.stream().__aiter__()
    while True:
        try:
            chunk = await asyncio.wait_for(anext(iterator), timeout=30)
        except StopAsyncIteration:
            break
        except TimeoutError:
            fail("upload_timeout", "Icon upload timed out", 408)
        if len(data) + len(chunk) > ICON_LIMIT:
            fail("icon_too_large", "Custom icons must be at most 2 MB", 413)
        data.extend(chunk)
    try:
        return await run_in_threadpool(
            set_icon,
            files,
            session,
            csrf,
            identifier,
            expected_revision,
            data,
            request.state.request_id,
        )
    except OSError:
        fail("storage_unavailable", "Icon storage is temporarily unavailable", 503)


@router.delete("/items/{identifier}/icon", response_model=ItemView)
def remove_icon(identifier: uuid.UUID, data: RevisionInput, request: Request):
    files, session, csrf = service(request, True)
    with files.transaction(session, csrf, mutation=True) as (connection, actor):
        row = files.live(connection, identifier)
        files.revision(row, data.expected_revision)
        connection.execute(
            text(
                "UPDATE items SET icon_blob_id=NULL,revision=revision+1,updated_at=now() "
                "WHERE id=:id"
            ),
            {"id": identifier},
        )
        retire(connection, row["icon_blob_id"])
        result = files.view(files.raw(connection, identifier))
        files.audit(
            connection, actor["id"], "icon_update", result, request.state.request_id, {"removed": 1}
        )
    with suppress(Exception):
        clean_retired_icons(files)
    return result


@router.get("/items/{identifier}/icon")
def icon(identifier: uuid.UUID, request: Request):
    files, session, _ = service(request)
    with files.transaction(session) as (connection, _):
        row = files.live(connection, identifier)
        blob = (
            connection.execute(
                text("SELECT * FROM blobs WHERE id=:id AND state='durable'"),
                {"id": row["icon_blob_id"]},
            )
            .mappings()
            .first()
        )
        if not blob:
            fail()
        with files.store.open(blob["storage_key"], blob["size_bytes"]) as stream:
            data = stream.read(ICON_LIMIT + 1)
        if len(data) > ICON_LIMIT:
            fail()
        return Response(data, media_type="image/png", headers=SAFE_HEADERS)


def byte_range(header, size):
    if not header:
        return 0, size - 1, 200
    if len(header) > 120:
        return None
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", header)
    if not match or not any(match.groups()) or size < 1:
        return None
    start, end = match.groups()
    if start:
        first, last = int(start), min(int(end) if end else size - 1, size - 1)
    else:
        first, last = max(0, size - int(end)), size - 1
    return (first, last, 206) if 0 <= first <= last < size else None


@router.get("/items/{identifier}/preview")
def preview(identifier: uuid.UUID, request: Request):
    files, session, _ = service(request)
    stream, item, _ = files.open_download(session, identifier)
    try:
        header = stream.read(4096)
        stream.seek(0)
        extension = item["name"].rsplit(".", 1)[-1].lower()
        if extension in {"png", "jpg", "jpeg", "webp"}:
            if item["size_bytes"] > IMAGE_LIMIT:
                fail(
                    "preview_too_large",
                    "Image previews support files up to 10 MB; download the original",
                    413,
                )
            return Response(
                raster(stream.read(IMAGE_LIMIT + 1)), media_type="image/png", headers=SAFE_HEADERS
            )
        media_type = None
        if extension == "pdf" and header.startswith(b"%PDF-"):
            if item["size_bytes"] > PDF_LIMIT:
                fail(
                    "preview_too_large",
                    "PDF previews support files up to 25 MB; download the original",
                    413,
                )
            media_type = "application/pdf"
        elif extension == "mp4" and header[4:8] == b"ftyp" and len(header) >= 12:
            media_type = "video/mp4"
        elif extension == "webm" and header.startswith(b"\x1aE\xdf\xa3") and b"webm" in header:
            media_type = "video/webm"
        if not media_type:
            fail(
                "preview_unsupported", "Preview unavailable for this file. Download it to open", 415
            )
        selected = byte_range(request.headers.get("range"), item["size_bytes"])
        if selected is None:
            return Response(
                status_code=416,
                headers={**SAFE_HEADERS, "Content-Range": f"bytes */{item['size_bytes']}"},
            )
        first, last, status = selected
        headers = {
            **SAFE_HEADERS,
            "Accept-Ranges": "bytes",
            "Content-Length": str(last - first + 1),
            "Content-Disposition": 'attachment; filename="preview"',
        }
        if status == 206:
            headers["Content-Range"] = f"bytes {first}-{last}/{item['size_bytes']}"
        stream.seek(first)

        def chunks(descriptor=stream):
            remaining = last - first + 1
            try:
                while remaining:
                    chunk = descriptor.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
            finally:
                descriptor.close()

        result = PreviewStream(
            stream, chunks(), status_code=status, media_type=media_type, headers=headers
        )
        stream = None  # generator owns it through its captured descriptor below
        return result
    finally:
        if stream:
            stream.close()
