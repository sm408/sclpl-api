"""Requests API routes.

Provides CRUD for requests, execution (send), and request-specific
history retrieval.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends

from app.core.models.context import ExecutionContext
from app.core.models.environment import Environment, Variable, VariableScope
from app.core.models.request import HttpMethod, RequestDef, RequestParam
from app.services.collection_service import RequestRepository
from app.services.environment_service import EnvironmentRepository
from app.services.history_service import HistoryRepository
from app.services.request_executor import HttpRequestExecutor
from app.web.converters import history_to_response, request_to_response
from app.web.deps import _get_environment_repo, _get_executor, _get_history_repo, _get_request_repo
from app.web.dto import (
    ExecuteRequest,
    PaginatedResponse,
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
    items = [request_to_response(r) for r in reqs]
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
    return RequestResponse.model_validate(request_to_response(created))


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
    return RequestResponse.model_validate(request_to_response(req))


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
    return RequestResponse.model_validate(request_to_response(updated))


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
    return RequestResponse.model_validate(request_to_response(moved))


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
    env_repo: EnvironmentRepository = Depends(_get_environment_repo),  # noqa: B008
) -> RunResultResponse:
    """Execute an HTTP request and return the result.

    Also saves the result to history. Loads the active environment's
    variables and merges them with explicitly-passed variables.
    """
    req_data = await repo.get(request_id)
    if not req_data or req_data.get("project_id") != project_id:
        raise NotFoundError(message=f"Request '{request_id}' not found.")

    request_def = _dto_to_request_def(req_data, request_id=request_id, project_id=project_id)
    ctx = ExecutionContext(request=request_def)

    # Load active environment and build variable map
    active_env = await env_repo.get_active(project_id=project_id)
    env_variable_map: dict[str, str] = {}
    if active_env:
        variables = []
        for v in active_env.get("variables", []):
            variables.append(Variable(
                key=v["key"],
                value=v["value"],
                scope=VariableScope(v.get("scope", "environment")),
                is_secret=bool(v.get("is_secret", 0)),
                enabled=bool(v.get("enabled", 1)),
            ))
        env_model = Environment(
            id=active_env["id"],
            name=active_env["name"],
            variables=variables,
            is_active=bool(active_env.get("is_active", 0)),
        )
        ctx.environment = env_model
        for v in variables:
            if v.enabled:
                env_variable_map[v.key] = v.value

    # Merge: env vars as base, explicit vars override
    merged = {**env_variable_map}
    if body and body.variables:
        merged.update(body.variables)
    ctx.variables = merged

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
    items = [history_to_response(r) for r in rows]
    return PaginatedResponse(items=items, total=len(items))
