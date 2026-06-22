"""Data Transfer Objects for the web API.

All DTOs use camelCase aliases so the JSON wire format is camelCase
while Python code uses snake_case.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(string: str) -> str:
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class CamelModel(BaseModel):
    """Base model that serialises to/from camelCase."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )


# ── Error protocol ──────────────────────────────────────────────────────


class FieldError(CamelModel):
    field: str
    message: str


class ErrorBody(CamelModel):
    code: str
    message: str
    field_errors: list[FieldError] = Field(default_factory=list)
    correlation_id: str = ""


class ErrorResponse(CamelModel):
    error: ErrorBody


# ── Pagination ──────────────────────────────────────────────────────────


class PaginatedResponse(CamelModel):
    """Standard envelope for list endpoints."""

    items: list[Any]
    next_cursor: str | None = None
    total: int = 0


# ── Health ──────────────────────────────────────────────────────────────


class HealthResponse(CamelModel):
    status: str
    version: str
    schema_version: int


# ── Project DTOs ────────────────────────────────────────────────────────


class ProjectCreate(CamelModel):
    name: str
    description: str = ""


class ProjectUpdate(CamelModel):
    name: str | None = None
    description: str | None = None


class ProjectResponse(CamelModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: str
    name: str
    description: str = ""
    root_path: str = ""
    is_default: bool = False
    created_at: str | None = None
    updated_at: str | None = None
