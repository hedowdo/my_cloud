"""Bounded metadata contracts; uploaded bytes are never interpreted as executable content."""

import unicodedata
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.identity_security import AuthError, StrictInput

ROOT_ID = UUID("00000000-0000-0000-0000-000000000001")
FILE_LIMIT = 500_000_000
FILE_ACTIONS = (
    "upload",
    "download",
    "rename",
    "move",
    "folder_create",
    "replace",
    "trash",
    "restore",
    "permanent_delete",
    "icon_update",
)


def clean_name(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    if (
        not value
        or value in {".", ".."}
        or value != value.strip()
        or value.endswith(".")
        or len(value) > 255
        or len(value.encode("utf-8")) > 255
        or any(char in "/\\:" or unicodedata.category(char).startswith("C") for char in value)
    ):
        raise ValueError("Use a name of 1-255 UTF-8 bytes without path or control characters")
    return value


class NamedInput(StrictInput):
    name: str

    _name = field_validator("name")(clean_name)


class FolderInput(NamedInput):
    parent_id: UUID = ROOT_ID
    collision: Literal["error", "keep_both"] = "error"


class UploadInput(NamedInput):
    parent_id: UUID = ROOT_ID
    size_bytes: int = Field(ge=0, le=FILE_LIMIT, strict=True)
    collision: Literal["error", "keep_both", "replace", "cancel"] = "error"
    target_id: UUID | None = None
    expected_revision: int | None = Field(default=None, ge=1, strict=True)
    confirm_replace: bool = False


class RevisionInput(StrictInput):
    expected_revision: int = Field(ge=1, strict=True)


class MoveInput(RevisionInput):
    name: str | None = None
    parent_id: UUID | None = None
    collision: Literal["error", "keep_both"] = "error"

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        return clean_name(value) if value is not None else value


class DeleteInput(RevisionInput):
    confirm: Literal[True]


class ItemView(BaseModel):
    has_icon: bool = False
    id: UUID
    parent_id: UUID | None
    kind: Literal["file", "folder"]
    name: str
    revision: int
    uploader_id: UUID | None
    size_bytes: int | None
    checksum_sha256: str | None
    created_at: datetime
    updated_at: datetime
    trashed_at: datetime | None
    replacement_of: UUID | None


class StorageView(BaseModel):
    used_bytes: int
    reserved_bytes: int
    pool_bytes: int
    available_bytes: int
    warning_percent: Literal[80, 90] | None


class ActivityView(BaseModel):
    id: UUID
    actor_id: UUID
    action: str
    target_id: UUID
    target_name: str
    occurred_at: datetime
    details: dict[str, str | int]


class DeletionView(BaseModel):
    id: UUID
    target_id: UUID
    state: Literal["pending", "complete"]
    last_error: Literal["storage_unavailable"] | None
    item_count: int
    created_at: datetime
    completed_at: datetime | None


def fail(code="item_unavailable", message="Item unavailable", status=404):
    raise AuthError(status, code, message)
