import secrets

import pytest


@pytest.fixture(autouse=True)
def identity_test_environment(monkeypatch):
    monkeypatch.setenv("AUTH_RATE_SECRET", secrets.token_hex(32))
    monkeypatch.setenv("ALLOWED_ORIGINS", '["https://testserver"]')
    monkeypatch.setenv("INSECURE_LOOPBACK_COOKIES", "false")
