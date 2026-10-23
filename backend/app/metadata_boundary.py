"""Bound actual identity request bytes before JSON parsing, including chunked bodies."""

import uuid

from starlette.responses import JSONResponse


class MetadataBoundary:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PATCH", "PUT", "DELETE"}:
            return await self.app(scope, receive, send)
        if not (
            scope["path"] == "/api/folders"
            or scope["path"].startswith(
                (
                    "/api/auth/",
                    "/api/admin/",
                    "/api/users/",
                    "/api/items/",
                    "/api/trash/",
                    "/api/folders/",
                )
            )
        ):
            return await self.app(scope, receive, send)
        if scope["method"] == "PUT" and scope["path"].endswith("/icon"):
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        status = (
            415
            if headers.get(b"content-type", b"").split(b";")[0].strip() != b"application/json"
            else 0
        )
        body = bytearray()
        while not status:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > 16384:
                status = 413
                break
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        if status:
            request_id = scope.get("state", {}).get("request_id", str(uuid.uuid4()))
            response = JSONResponse(
                {
                    "error": {
                        "code": "request_too_large" if status == 413 else "json_required",
                        "message": "Send a small JSON request",
                        "request_id": request_id,
                    }
                },
                status_code=status,
            )
            return await response(scope, receive, send)

        async def buffered():
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, buffered, send)
