import io
import sys

import pytest

from app import bootstrap
from app.identity_security import AuthError, Passwords, digest, token, valid_token


def test_bootstrap_refuses_redirected_password_input(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("synthetic input"))
    with pytest.raises(SystemExit, match="Run interactively"):
        bootstrap.main()


def test_password_work_is_bounded_and_tokens_are_independent():
    passwords = Passwords()
    assert passwords.slots.acquire(blocking=False)
    assert passwords.slots.acquire(blocking=False)
    try:
        with pytest.raises(AuthError) as error:
            passwords.verify(None, "synthetic test")
        assert error.value.status == 429
    finally:
        passwords.slots.release()
        passwords.slots.release()
    first, second = token(), token()
    assert valid_token(first) and valid_token(second) and first != second
    assert len(digest(first)) == 32 and digest(first) != digest(second)
    assert not passwords.verify("invalid-hash", "synthetic test")
