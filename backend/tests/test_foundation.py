import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app, logger


def test_liveness_does_not_depend_on_database_and_errors_are_private(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://probe:private-marker@127.0.0.1:1/missing",
        storage_root=tmp_path,
    )
    with TestClient(create_app(settings)) as client:
        live = client.get("/api/health/live", headers={"X-Request-ID": "untrusted-user-input"})
        assert live.status_code == 200
        assert live.json() == {"status": "ok"}
        assert live.headers["X-Request-ID"] != "untrusted-user-input"
        assert live.headers["Cache-Control"] == "no-store"
        unavailable = client.get("/api/health/ready")
        assert unavailable.status_code == 503
        assert unavailable.json() == {"status": "unavailable"}
        assert "private-marker" not in unavailable.text
        assert "127.0.0.1" not in unavailable.text
        assert "SELECT" not in unavailable.text
        # No unprotected feature routes accidentally exposed before authentication exists.
        assert client.get("/api/items").status_code == 401
        schema = client.get("/openapi.json").json()
        assert {
            "/api/health/live",
            "/api/health/ready",
            "/api/auth/login",
            "/api/admin/users",
        } <= set(schema["paths"])


def test_production_refuses_unsafe_configuration_before_storage_creation(tmp_path: Path):
    storage = tmp_path / "must-not-be-created"
    with pytest.raises(ValidationError, match="cloud_app"):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+psycopg://probe:fixture@127.0.0.1:1/missing",
            storage_root=storage,
            allowed_origins=["https://fixture.duckdns.org"],
        )
    assert not storage.exists()


def test_invalid_connection_configuration_does_not_echo_input():
    with pytest.raises(ValidationError) as failure:
        Settings(_env_file=None, database_url="fixture-private-input")
    assert "fixture-private-input" not in str(failure.value)


def test_request_logging_omits_private_headers_and_query(tmp_path: Path, caplog):
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://probe:fixture@127.0.0.1:1/missing",
        storage_root=tmp_path,
    )
    logger.addHandler(caplog.handler)
    try:
        with TestClient(create_app(settings)) as client:
            response = client.get(
                "/api/health/live?token=fixture-query-secret",
                headers={
                    "Authorization": "Bearer fixture-header-secret",
                    "X-Request-ID": "fixture-client-controlled-id",
                },
            )
    finally:
        logger.removeHandler(caplog.handler)
    records = [record.getMessage() for record in caplog.records if record.name == logger.name]
    assert records
    serialized = "\n".join(records)
    assert "fixture-query-secret" not in serialized
    assert "fixture-header-secret" not in serialized
    assert "fixture-client-controlled-id" not in serialized
    event = json.loads(records[-1])
    assert event["request_id"] == response.headers["X-Request-ID"]
    assert event["status"] == 200
    assert event["timestamp"].endswith("Z")


@pytest.mark.parametrize(
    "overrides",
    [
        {"auth_rate_secret": "short"},
        {"insecure_loopback_cookies": True, "allowed_origins": ["http://example.com"]},
        {
            "insecure_loopback_cookies": True,
            "app_env": "production",
            "allowed_origins": ["http://127.0.0.1"],
        },
        {"allowed_origins": ["https://example.com/path"]},
        {"allowed_origins": []},
    ],
)
def test_identity_configuration_fails_closed(overrides):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://probe:fixture@127.0.0.1:1/missing",
            **overrides,
        )
