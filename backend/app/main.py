import json
import logging
import tempfile
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from app import file_media, file_positions, file_queries  # noqa: F401 - register approved routes
from app.config import Settings
from app.database import SCHEMA_REVISION, make_engine
from app.file_routes import router as file_router
from app.file_service import Files
from app.identity_routes import clear_cookies, router
from app.identity_security import AuthError
from app.identity_service import Identity
from app.metadata_boundary import MetadataBoundary

logger = logging.getLogger("personal_cloud")
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)
logger.propagate = False


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configured = settings or Settings()
        configured.storage_root.mkdir(parents=True, exist_ok=True)
        application.state.settings = configured
        application.state.engine = make_engine(configured)
        application.state.identity = Identity(application.state.engine, configured)
        application.state.files = Files(
            application.state.engine, application.state.identity, configured
        )
        # Liveness still works during DB outage; uploads reconcile before reserving.
        with suppress(Exception):
            await run_in_threadpool(application.state.files.reconcile)
        try:
            yield
        finally:
            application.state.engine.dispose()

    application = FastAPI(
        title="Personal Cloud API",
        version="0.1.0",
        lifespan=lifespan,
        description="Private identity and durable shared file operations.",
    )
    application.include_router(router)
    application.include_router(file_router)
    application.add_middleware(MetadataBoundary)

    @application.exception_handler(AuthError)
    async def identity_error(request: Request, exc: AuthError):
        response = JSONResponse(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "request_id": request.state.request_id,
                }
            },
            status_code=exc.status,
        )
        if exc.status == 429:
            response.headers["Retry-After"] = "900"
        if exc.code == "authentication_required":
            clear_cookies(response, application.state.settings)
        return response

    @application.middleware("http")
    async def request_context(request: Request, call_next: Callable):
        # Generate our own ID; never echo arbitrary client headers or URLs into logs.
        request.state.request_id = str(uuid.uuid4())
        started = time.monotonic()
        try:
            allowed_hosts = {
                urlsplit(origin).hostname for origin in application.state.settings.allowed_origins
            }
            # Loopback health probes remain local; arbitrary Host values cannot use the API.
            allowed_hosts.update({"127.0.0.1", "localhost", "::1"})
            if request.url.hostname not in allowed_hosts:
                response = JSONResponse(
                    {
                        "error": {
                            "code": "host_failed",
                            "message": "Request host is not allowed",
                            "request_id": request.state.request_id,
                        }
                    },
                    status_code=400,
                )
            else:
                response = await call_next(request)
        except Exception:
            logger.error(
                json.dumps(
                    {
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "severity": "ERROR",
                        "event": "request_failed",
                        "request_id": request.state.request_id,
                    }
                )
            )
            response = JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "internal_error",
                        "message": "Request failed",
                        "request_id": request.state.request_id,
                    }
                },
            )
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        logger.info(
            json.dumps(
                {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "severity": "INFO",
                    "event": "request_finished",
                    "request_id": request.state.request_id,
                    "method": request.method,
                    "status": response.status_code,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                }
            )
        )
        return response

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_request",
                    "message": "Check the supplied request fields",
                    "request_id": request.state.request_id,
                }
            },
        )

    @application.get("/api/health/live", tags=["health"])
    def live() -> dict[str, str]:
        return {"status": "ok"}

    def dependencies_ready() -> bool:
        try:
            with application.state.engine.connect() as connection:
                revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
                if revision != SCHEMA_REVISION:
                    return False
            # A short real write catches missing/unwritable file-volume mounts.
            with tempfile.TemporaryFile(dir=application.state.settings.storage_root) as probe:
                probe.write(b"ready")
                probe.flush()
            return True
        except Exception:
            # No DSN, exception text, filesystem paths or credentials in public output/logs.
            return False

    @application.get("/api/health/ready", tags=["health"])
    async def ready() -> JSONResponse:
        healthy = await run_in_threadpool(dependencies_ready)
        return JSONResponse(
            {"status": "ready" if healthy else "unavailable"},
            status_code=200 if healthy else 503,
        )

    return application


app = create_app()
