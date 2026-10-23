from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app


def production_settings(tmp_path: Path, **overrides):
    values = {
        "_env_file": None,
        "app_env": "production",
        "database_url": "postgresql+psycopg://cloud_app:fixture@127.0.0.1:1/missing",
        "storage_root": tmp_path,
        "allowed_origins": ["https://fixture.duckdns.org"],
    }
    return Settings(**(values | overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"app_env": "prodution"},
        {"allowed_origins": ["http://fixture.duckdns.org"]},
        {"allowed_origins": ["https://fixture.duckdns.org:8443"]},
        {"allowed_origins": ["https://127.0.0.1"]},
        {"allowed_origins": ["https://localhost"]},
        {"allowed_origins": ["https://cloud.local"]},
        {"allowed_origins": ["https://one.example.com", "https://two.example.com"]},
        {"storage_root": Path("relative/storage")},
        {"database_url": "postgresql+psycopg://postgres:fixture@127.0.0.1:1/missing"},
        {"insecure_loopback_cookies": True},
    ],
)
def test_production_rejects_unsafe_defaults(tmp_path, overrides):
    with pytest.raises(ValidationError):
        production_settings(tmp_path, **overrides)


def test_production_starts_with_secure_settings_and_enforces_host(tmp_path):
    settings = production_settings(tmp_path)
    assert settings.session_cookie == "__Host-pc_session"
    assert settings.csrf_cookie == "__Host-pc_csrf"
    with TestClient(create_app(settings), base_url="https://fixture.duckdns.org") as client:
        assert client.get("/api/health/live").status_code == 200
        assert client.get("/api/health/ready").status_code == 503
        assert client.get("/api/items").status_code == 401
        assert (
            client.get("/api/health/live", headers={"Host": "attacker.example.com"}).status_code
            == 400
        )
