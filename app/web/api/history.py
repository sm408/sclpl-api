"""History API routes.

Provides cursor-paginated request execution history scoped to a project.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query

from app.services.history_service import HistoryRepository
from app.web.deps import _get_history_repo
from app.web.dto import HistoryResponse, PaginatedResponse
from app.web.errors import NotFoundError

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/history",
    tags=["history"],
)


def _to_response(row: dict) -> dict:
    """Convert a raw history dict from DB to a camelCase response dict."""
    response_headers = row.get("response_headers", "{}")
    if isinstance(response_headers, str):
        try:
            response_headers = json.loads(response_headers)
        except (json.JSONDecodeError, TypeError):
            response_headers = {}
    variables_used = row.get("variables_used", "{}")
    if isinstance(variables_used, str):
        try:
            variables_used = json.loads(variables_used)
        except (json.JSONDecodeError, TypeError):
            variables_used = {}
    return HistoryResponse(
        id=row["id"],
        project_id=row.get("project_id", ""),
        request_id=row.get("request_id"),
        request_name=row.get("request_name", ""),
        method=row.get("method", ""),
        url=row.get("url", ""),
        status=row.get("status", ""),
        status_code=row.get("status_code"),
        response_body=row.get("response_body"),
        response_headers=response_headers if isinstance(response_headers, dict) else {},
        duration_ms=row.get("duration_ms", 0),
        error_message=row.get("error_message"),
        environment_id=row.get("environment_id"),
        variables_used=variables_used if isinstance(variables_used, dict) else {},
        created_at=row.get("created_at"),
    ).model_dump(by_alias=True)


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
    items = [_to_response(r) for r in rows]
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
    return HistoryResponse.model_validate(_to_response(row))


@router.delete("", status_code=200)
async def clear_history(
    project_id: str,
    repo: HistoryRepository = Depends(_get_history_repo),  # noqa: B008
) -> dict:
    """Clear all history for a project. Returns the number of deleted entries."""
    count = await repo.clear(project_id=project_id)
    return {"deleted": count}
