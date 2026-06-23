"""Requests API routes.

Provides CRUD for requests, execution (send), and request-specific
history retrieval.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends

from app.core.models.context import ExecutionContext
from app.core.models.request import HttpMethod, RequestDef, RequestParam
from app.services.collection_service import RequestRepository
from app.services.history_service import HistoryRepository
from app.services.request_executor import HttpRequestExecutor
from app.web.deps import _get_executor, _get_history_repo, _get_request_repo
from app.web.dto import (
    ExecuteRequest,
    HistoryResponse,
    PaginatedResponse,
    ParamDto,
    RequestCreate,
    RequestResponse,
    RequestUpdate,
    RunResultResponse,
)
from app.web.errors import ConflictError, NotFoundError, ValidationError

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/requests",
    tags=["requests"],
)


def _to_response(req: dict) -> dict:
    """Convert a raw request dict from DB to a camelCase response dict."""
    headers = req.get("headers", "[]")
    if isinstance(headers, str):
        try:
            headers = json.loads(headers)
        except (json.JSONDecodeError, TypeError):
            headers = []
    query_params = req.get("query_params", "[]")
    if isinstance(query_params, str):
        try:
            query_params = json.loads(query_params)
        except (json.JSONDecodeError, TypeError):
            query_params = []
    auth_config = req.get("auth_config", "{}")
    if isinstance(auth_config, str):
        try:
            auth_config = json.loads(auth_config)
        except (json.JSONDecodeError, TypeError):
            auth_config = {}

    return RequestResponse(
        id=req["id"],
        project_id=req.get("project_id", ""),
        collection_id=req.get("collection_id"),
        name=req["name"],
        method=req.get("method", "GET"),
        url=req.get("url", ""),
        headers=[ParamDto(**h) for h in headers] if isinstance(headers, list) else [],
        query_params=[ParamDto(**p) for p in query_params] if isinstance(query_params, list) else [],
        body=req.get("body"),
        body_type=req.get("body_type"),
        auth_type=req.get("auth_type"),
        auth_config=auth_config if isinstance(auth_config, dict) else {},
        revision=req.get("revision", 1),
        created_at=req.get("created_at"),
        updated_at=req.get("updated_at"),
    ).model_dump(by_alias=True)


def _history_to_response(row: dict) -> dict:
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


def _dto_to_request_def(data: dict, request_id: str = "", project_id: str = "") -> RequestDef:
    """Convert a raw request dict (from DB or DTO) to a RequestDef model."""
    headers_raw = data.get("headers", [])
    if isinstance(headers_raw, str):
        try:
            headers_raw = json.loads(headers_raw)
        except (json.JSONDecodeError, TypeError):
            headers_raw = []
    params_raw = data.get("query_params", [])
    if isinstance(params_raw, str):
        try:
            params_raw = json.loads(params_raw)
        except (json.JSONDecodeError, TypeError):
            params_raw = []

    method_str = data.get("method", "GET")
    try:
        method = HttpMethod(method_str)
    except ValueError:
        method = HttpMethod.GET

    headers = [
        RequestParam(key=h.get("key", ""), value=h.get("value", ""), enabled=h.get("enabled", True))
        for h in headers_raw
        if isinstance(h, dict)
    ]
    params = [
        RequestParam(key=p.get("key", ""), value=p.get("value", ""), enabled=p.get("enabled", True))
        for p in params_raw
        if isinstance(p, dict)
    ]
    auth_config = data.get("auth_config", {})
    if isinstance(auth_config, str):
        try:
            auth_config = json.loads(auth_config)
        except (json.JSONDecodeError, TypeError):
            auth_config = {}

    return RequestDef(
        id=request_id or data.get("id", ""),
        name=data.get("name", ""),
        method=method,
        url=data.get("url", ""),
        headers=headers,
        query_params=params,
        body=data.get("body"),
        body_type=data.get("body_type"),
        auth_type=data.get("auth_type"),
        auth_config=auth_config if isinstance(auth_config, dict) else {},
        collection_id=data.get("collection_id"),
    )


@router.get("", response_model=PaginatedResponse)
async def list_requests(
    project_id: str,
    collection_id: str | None = None,
    repo: RequestRepository = Depends(_get_request_repo),  # noqa: B008
) -> PaginatedResponse:
    """List requests, optionally filtered by collection."""
    reqs = await repo.list_all(collection_id=collection_id, project_id=project_id)
    items = [_to_response(r) for r in reqs]
    return PaginatedResponse(items=items, total=len(items))


@router.post("", response_model=RequestResponse, status_code=201)
async def create_request(
    project_id: str,
    body: RequestCreate,
    repo: RequestRepository = Depends(_get_request_repo),  # noqa: B008
) -> RequestResponse:
    """Create a new request."""
    if not body.name or not body.name.strip():
        raise ValidationError(
            message="Request name is required.",
            field_errors=[{"field": "name", "message": "Request name is required."}],
        )
    data = {
        "name": body.name,
        "method": body.method,
        "url": body.url,
        "collection_id": body.collection_id,
        "headers": [p.model_dump() for p in body.headers],
        "query_params": [p.model_dump() for p in body.query_params],
        "body": body.body,
        "body_type": body.body_type,
        "auth_type": body.auth_type,
        "auth_config": body.auth_config,
        "project_id": project_id,
    }
    created = await repo.create(data)
    return RequestResponse.model_validate(_to_response(created))


@router.get("/{request_id}", response_model=RequestResponse)
async def get_request(
    project_id: str,
    request_id: str,
    repo: RequestRepository = Depends(_get_request_repo),  # noqa: B008
) -> RequestResponse:
    """Get a single request."""
    req = await repo.get(request_id)
    if not req or req.get("project_id") != project_id:
        raise NotFoundError(message=f"Request '{request_id}' not found.")
    return RequestResponse.model_validate(_to_response(req))


@router.patch("/{request_id}", response_model=RequestResponse)
async def update_request(
    project_id: str,
    request_id: str,
    body: RequestUpdate,
    repo: RequestRepository = Depends(_get_request_repo),  # noqa: B008
) -> RequestResponse:
    """Update a request. Supports revision-based conflict detection."""
    existing = await repo.get(request_id)
    if not existing or existing.get("project_id") != project_id:
        raise NotFoundError(message=f"Request '{request_id}' not found.")

    data = body.model_dump(exclude_unset=True, by_alias=False)
    revision = data.pop("revision", None)

    # Convert ParamDto lists to plain dicts for storage
    if "headers" in data and data["headers"] is not None:
        data["headers"] = [
            p.model_dump() if hasattr(p, "model_dump") else p
            for p in data["headers"]
        ]
    if "query_params" in data and data["query_params"] is not None:
        data["query_params"] = [
            p.model_dump() if hasattr(p, "model_dump") else p
            for p in data["query_params"]
        ]

    if not data:
        raise ValidationError(
            message="At least one field must be provided.",
            field_errors=[{"field": "body", "message": "At least one field must be provided."}],
        )

    updated = await repo.update(request_id, data, revision=revision)
    if not updated:
        raise ConflictError(
            message="Revision conflict — the request was modified by another client."
        )
    return RequestResponse.model_validate(_to_response(updated))


@router.post("/{request_id}/move", response_model=RequestResponse)
async def move_request(
    project_id: str,
    request_id: str,
    target_collection_id: str | None = None,
    repo: RequestRepository = Depends(_get_request_repo),  # noqa: B008
) -> RequestResponse:
    """Move a request to a different collection (or unassign)."""
    existing = await repo.get(request_id)
    if not existing or existing.get("project_id") != project_id:
        raise NotFoundError(message=f"Request '{request_id}' not found.")
    moved = await repo.move(request_id, target_collection_id)
    if not moved:
        raise NotFoundError(message=f"Request '{request_id}' not found.")
    return RequestResponse.model_validate(_to_response(moved))


@router.delete("/{request_id}", status_code=204)
async def delete_request(
    project_id: str,
    request_id: str,
    repo: RequestRepository = Depends(_get_request_repo),  # noqa: B008
) -> None:
    """Delete a request."""
    existing = await repo.get(request_id)
    if not existing or existing.get("project_id") != project_id:
        raise NotFoundError(message=f"Request '{request_id}' not found.")
    success = await repo.delete(request_id)
    if not success:
        raise NotFoundError(message=f"Request '{request_id}' not found.")


# ── Execute ─────────────────────────────────────────────────────────────


@router.post("/{request_id}/execute", response_model=RunResultResponse)
async def execute_request(
    project_id: str,
    request_id: str,
    body: ExecuteRequest | None = None,
    repo: RequestRepository = Depends(_get_request_repo),  # noqa: B008
    executor: HttpRequestExecutor = Depends(_get_executor),  # noqa: B008
    history_repo: HistoryRepository = Depends(_get_history_repo),  # noqa: B008
) -> RunResultResponse:
    """Execute an HTTP request and return the result.

    Also saves the result to history.
    """
    req_data = await repo.get(request_id)
    if not req_data or req_data.get("project_id") != project_id:
        raise NotFoundError(message=f"Request '{request_id}' not found.")

    request_def = _dto_to_request_def(req_data, request_id=request_id, project_id=project_id)
    ctx = ExecutionContext(request=request_def)
    if body and body.variables:
        ctx.variables = body.variables

    result, entry = await executor.execute_with_history(request_def, ctx)
    await history_repo.save(entry, project_id=project_id)

    return RunResultResponse(
        status_code=result.status_code,
        headers=result.headers,
        body=result.body,
        duration_ms=result.duration_ms,
        error=result.error,
    )


# ── Request-specific history ────────────────────────────────────────────


@router.get("/{request_id}/history", response_model=PaginatedResponse)
async def list_request_history(
    project_id: str,
    request_id: str,
    limit: int = 20,
    repo: RequestRepository = Depends(_get_request_repo),  # noqa: B008
    history_repo: HistoryRepository = Depends(_get_history_repo),  # noqa: B008
) -> PaginatedResponse:
    """List execution history for a specific request."""
    existing = await repo.get(request_id)
    if not existing or existing.get("project_id") != project_id:
        raise NotFoundError(message=f"Request '{request_id}' not found.")
    rows = await history_repo.list_by_request(request_id, limit=limit)
    items = [_history_to_response(r) for r in rows]
    return PaginatedResponse(items=items, total=len(items))
