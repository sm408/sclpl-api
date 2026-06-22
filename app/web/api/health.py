"""Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.storage.db import SCHEMA_VERSION, Database
from app.web.deps import _get_db
from app.web.dto import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(db: Database = Depends(_get_db)) -> HealthResponse:  # noqa: B008
    """Liveness and readiness probe."""
    return HealthResponse(
        status="ok",
        version="0.1.0",
        schema_version=SCHEMA_VERSION,
    )
