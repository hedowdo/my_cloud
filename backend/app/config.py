from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    app_env: Literal["development", "production"] = "development"
    database_url: SecretStr
    migration_database_url: SecretStr | None = None
    storage_root: Path = Path(".local/storage")
    auth_rate_secret: SecretStr
    allowed_origins: list[str] = ["http://127.0.0.1:8080", "http://127.0.0.1:5173"]
    insecure_loopback_cookies: bool = False
    storage_pool_bytes: int = Field(default=1_000_000_000, ge=1)
    storage_reserve_bytes: int = Field(default=2_000_000_000, ge=0)

    @field_validator("auth_rate_secret")
    @classmethod
    def require_auth_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("AUTH_RATE_SECRET must contain at least 32 characters")
        return value

    @model_validator(mode="after")
    def validate_origins(self):
        if not self.allowed_origins:
            raise ValueError("At least one exact origin is required")
        for value in self.allowed_origins:
            origin = urlsplit(value)
            if (
                origin.scheme not in {"http", "https"}
                or not origin.hostname
                or origin.username
                or origin.password
                or origin.path
                or origin.query
                or origin.fragment
                or value.endswith("/")
            ):
                raise ValueError("Allowed origins must be exact HTTP(S) origins")
            if self.insecure_loopback_cookies and (
                self.app_env != "development"
                or origin.scheme != "http"
                or origin.hostname not in {"127.0.0.1", "localhost", "::1"}
            ):
                raise ValueError("Insecure cookies are restricted to explicit development loopback")
        if self.app_env == "production":
            origin = urlsplit(self.allowed_origins[0])
            if (
                len(self.allowed_origins) != 1
                or origin.scheme != "https"
                or origin.port not in {None, 443}
                or "." not in (origin.hostname or "")
                or origin.hostname.endswith((".localhost", ".local", ".internal", ".test"))
                or origin.hostname.replace(".", "").isdigit()
            ):
                raise ValueError("Production requires one public HTTPS origin on port 443")
            if not self.storage_root.is_absolute():
                raise ValueError("Production storage root must be absolute")
            if make_url(self.database_url.get_secret_value()).username != "cloud_app":
                raise ValueError("Production runtime requires the cloud_app database role")
        return self

    @property
    def session_cookie(self) -> str:
        return "pc_session_dev" if self.insecure_loopback_cookies else "__Host-pc_session"

    @property
    def csrf_cookie(self) -> str:
        return "pc_csrf_dev" if self.insecure_loopback_cookies else "__Host-pc_csrf"

    @field_validator("database_url")
    @classmethod
    def require_postgresql(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except Exception:
            raise ValueError("DATABASE_URL must be a valid PostgreSQL connection URL") from None
        if url.drivername != "postgresql+psycopg":
            raise ValueError("DATABASE_URL must use postgresql+psycopg")
        return value
