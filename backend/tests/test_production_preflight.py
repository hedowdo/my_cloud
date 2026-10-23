import secrets

import pytest
from scripts.production_preflight import read_configuration, validate_configuration


def configuration():
    return {
        "CLOUD_HOST": "fixture.duckdns.org",
        "DATA_ROOT": "/srv/my-cloud-data",
        "DATABASE_IMAGE": "postgres@sha256:" + "a" * 64,
        "API_IMAGE": "cloud-api@sha256:" + "b" * 64,
        "FRONTEND_IMAGE": "cloud-frontend@sha256:" + "c" * 64,
        "POSTGRES_PASSWORD": secrets.token_hex(32),
        "MIGRATION_PASSWORD": secrets.token_hex(32),
        "APP_DATABASE_PASSWORD": secrets.token_hex(32),
        "AUTH_RATE_SECRET": secrets.token_hex(32),
        "STORAGE_POOL_BYTES": "100000000000",
        "STORAGE_RESERVE_BYTES": "10000000000",
    }


@pytest.mark.parametrize(
    "name,value",
    [
        ("CLOUD_HOST", "http://fixture.duckdns.org"),
        ("CLOUD_HOST", "fixture.local"),
        ("CLOUD_HOST", "-fixture.duckdns.org"),
        ("DATA_ROOT", "/"),
        ("DATA_ROOT", "/srv/../etc"),
        ("API_IMAGE", "cloud-api:latest"),
        ("POSTGRES_PASSWORD", "placeholder"),
        ("STORAGE_POOL_BYTES", "100000000001"),
        ("STORAGE_RESERVE_BYTES", "1000"),
    ],
)
def test_preflight_rejects_unsafe_release_configuration(name, value):
    values = configuration() | {name: value}
    with pytest.raises(ValueError):
        validate_configuration(values)


def test_preflight_accepts_pinned_configuration_and_refuses_reused_secret():
    values = configuration()
    validate_configuration(values)
    values["APP_DATABASE_PASSWORD"] = values["POSTGRES_PASSWORD"]
    with pytest.raises(ValueError, match="independent"):
        validate_configuration(values)


def test_configuration_parser_refuses_duplicate_or_expanded_entries(tmp_path):
    path = tmp_path / "private.env"
    for content in ("DATA_ROOT=/srv/data\nDATA_ROOT=/srv/other\n", "API_IMAGE=$(command)\n"):
        path.write_text(content, encoding="utf-8")
        with pytest.raises(ValueError):
            read_configuration(path)
