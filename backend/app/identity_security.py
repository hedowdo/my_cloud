"""Password and token primitives; no application secrets are logged."""

import hashlib
import re
import secrets
import threading
from typing import Literal

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr


class AuthError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class LoginInput(StrictInput):
    email: EmailStr = Field(max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)


class AccountInput(LoginInput):
    password: SecretStr = Field(min_length=12, max_length=128)


class RegisterInput(AccountInput):
    token: SecretStr = Field(min_length=43, max_length=43)


class DeactivateInput(StrictInput):
    active: Literal[False]


class ThemeInput(StrictInput):
    theme: Literal["light", "dark"]


def token() -> str:
    return secrets.token_urlsafe(32)


def digest(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


def valid_token(value: str | None) -> bool:
    return value is not None and re.fullmatch(r"[A-Za-z0-9_-]{43}", value) is not None


class Passwords:
    def __init__(self):
        self.hasher = PasswordHasher(
            type=Type.ID, memory_cost=65536, time_cost=3, parallelism=1, hash_len=32, salt_len=16
        )
        self.slots = threading.BoundedSemaphore(2)
        self.dummy = self.hasher.hash(secrets.token_urlsafe(32))

    def hash(self, password: str) -> str:
        if not self.slots.acquire(blocking=False):
            raise AuthError(429, "busy", "Please wait before trying again")
        try:
            return self.hasher.hash(password)
        finally:
            self.slots.release()

    def verify(self, encoded: str | None, password: str) -> bool:
        if not self.slots.acquire(blocking=False):
            raise AuthError(429, "busy", "Please wait before trying again")
        try:
            try:
                verified = self.hasher.verify(encoded or self.dummy, password)
                return bool(encoded) and verified
            except (InvalidHashError, VerificationError):
                return False
        finally:
            self.slots.release()
