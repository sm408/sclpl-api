"""History API routes.

Provides cursor-paginated request execution history scoped to a project.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.services.history_service import HistoryRepository
from app.web.converters import history_to_response
from app.web.deps import _get_history_repo
from app.web.dto import HistoryResponse, PaginatedResponse
from app.web.errors import NotFoundError

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/history",
    tags=["history"],
)


@router.get("", response_model=PaginatedResponse)
async def list_history(
    project_id: str,
    cursor: str | None = Query(None, description="Cursor for pagination (created_at of last item)"),
    limit: int = Query(50, ge=1, le=200, description="Max items per page"),
    request_id: str | None = Query(None, description="Filter by request ID"),
    repo: HistoryRepository = Depends(_get_history_repo),  # noqa: B008
) -> PaginatedResponse:
    """List execution history with cursor-based pagination."""
    rows, next_cursor = await repo.list_paginated(
        project_id,
        cursor=cursor,
        limit=limit,
        request_id=request_id,
    )
    total = await repo.count(project_id=project_id)
    items = [history_to_response(r) for r in rows]
    return PaginatedResponse(items=items, nextCursor=next_cursor, total=total)


@router.get("/{history_id}", response_model=HistoryResponse)
async def get_history_entry(
    project_id: str,
    history_id: str,
    repo: HistoryRepository = Depends(_get_history_repo),  # noqa: B008
) -> HistoryResponse:
    """Get a single history entry."""
    row = await repo.get(history_id)
    if not row or row.get("project_id") != project_id:
        raise NotFoundError(message=f"History entry '{history_id}' not found.")
    return HistoryResponse.model_validate(history_to_response(row))


@router.delete("", status_code=200)
async def clear_history(
    project_id: str,
    repo: HistoryRepository = Depends(_get_history_repo),  # noqa: B008
) -> dict:
    """Clear all history for a project. Returns the number of deleted entries."""
    count = await repo.clear(project_id=project_id)
    return {"deleted": count}
