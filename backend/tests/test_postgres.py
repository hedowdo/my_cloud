import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.config import Settings
from app.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def runtime_url():
    value = os.environ.get("TEST_RUNTIME_DATABASE_URL")
    if not value:
        pytest.skip("No disposable PostgreSQL configured; use scripts/verify_postgres.py")
    if not (make_url(value).database or "").startswith("cloud_test_"):
        pytest.fail("Refusing an integration database without cloud_test_ prefix")
    return value


def test_runtime_cannot_change_schema_and_constraints_hold(runtime_url: str):
    engine = create_engine(runtime_url, hide_parameters=True)
    with engine.connect() as connection:
        with pytest.raises(DBAPIError):
            connection.execute(text("CREATE TABLE forbidden_runtime_ddl (id integer)"))
        connection.rollback()
        assert connection.scalar(text("SELECT count(*) FROM items WHERE parent_id IS NULL")) == 1
        # The runtime account is not a database administrator or schema migrator.
        assert (
            connection.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname=current_user"))
            is False
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                text("""INSERT INTO blobs (id, storage_key, size_bytes, checksum_sha256, state)
                    VALUES (:id, :key, 500000001, :key, 'durable')"""),
                {"id": uuid.uuid4(), "key": "a" * 64},
            )
        connection.rollback()
        # Atomic transaction rollback cannot leave a partially created folder.
        folder_id = uuid.uuid4()
        connection.execute(
            text("""INSERT INTO items (id,parent_id,kind,name,name_key)
                VALUES (:id,'00000000-0000-0000-0000-000000000001','folder','probe','probe')"""),
            {"id": folder_id},
        )
        connection.rollback()
        assert (
            connection.scalar(text("SELECT count(*) FROM items WHERE id=:id"), {"id": folder_id})
            == 0
        )
    engine.dispose()


def test_ready_requires_migrated_database_and_file_volume(runtime_url: str, tmp_path: Path):
    settings = Settings(_env_file=None, database_url=runtime_url, storage_root=tmp_path)
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health/ready").status_code == 200
    # Recreating the application must not wipe the file volume or database.
    marker = tmp_path / "persisted.txt"
    marker.write_text("disposable verification", encoding="utf-8")
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health/ready").status_code == 200
    assert marker.read_text(encoding="utf-8") == "disposable verification"
