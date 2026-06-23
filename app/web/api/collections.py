"""Collections API routes.

Provides CRUD for collections scoped to a project, plus collection
duplication and tree structure retrieval.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.services.collection_service import CollectionRepository, RequestRepository
from app.web.deps import _get_collection_repo, _get_request_repo
from app.web.dto import (
    CollectionCreate,
    CollectionResponse,
    CollectionUpdate,
    PaginatedResponse,
    RequestResponse,
    ParamDto,
)
from app.web.errors import ConflictError, NotFoundError, ValidationError

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/collections",
    tags=["collections"],
)


def _to_response(col: dict) -> dict:
    """Convert a raw collection dict to a camelCase response dict."""
    return CollectionResponse(
        id=col["id"],
        project_id=col.get("project_id", ""),
        name=col["name"],
        description=col.get("description", ""),
        revision=col.get("revision", 1),
        created_at=col.get("created_at"),
        updated_at=col.get("updated_at"),
    ).model_dump(by_alias=True)


@router.get("", response_model=PaginatedResponse)
async def list_collections(
    project_id: str,
    repo: CollectionRepository = Depends(_get_collection_repo),  # noqa: B008
) -> PaginatedResponse:
    """List all collections for a project."""
    cols = await repo.list_all(project_id=project_id)
    items = [_to_response(c) for c in cols]
    return PaginatedResponse(items=items, total=len(items))


@router.post("", response_model=CollectionResponse, status_code=201)
async def create_collection(
    project_id: str,
    body: CollectionCreate,
    repo: CollectionRepository = Depends(_get_collection_repo),  # noqa: B008
) -> CollectionResponse:
    """Create a new collection in a project."""
    if not body.name or not body.name.strip():
        raise ValidationError(
            message="Collection name is required.",
            field_errors=[{"field": "name", "message": "Collection name is required."}],
        )
    col = await repo.create(name=body.name, description=body.description, project_id=project_id)
    return CollectionResponse.model_validate(
        {**col, "project_id": project_id}
    )


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    project_id: str,
    collection_id: str,
    repo: CollectionRepository = Depends(_get_collection_repo),  # noqa: B008
) -> CollectionResponse:
    """Get a single collection."""
    col = await repo.get(collection_id)
    if not col or col.get("project_id") != project_id:
        raise NotFoundError(message=f"Collection '{collection_id}' not found.")
    return CollectionResponse.model_validate(col)


@router.patch("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    project_id: str,
    collection_id: str,
    body: CollectionUpdate,
    repo: CollectionRepository = Depends(_get_collection_repo),  # noqa: B008
) -> CollectionResponse:
    """Update a collection's name and/or description."""
    data = body.model_dump(exclude_unset=True, by_alias=False)
    if not data:
        raise ValidationError(
            message="At least one field must be provided.",
            field_errors=[{"field": "body", "message": "At least one field must be provided."}],
        )
    existing = await repo.get(collection_id)
    if not existing or existing.get("project_id") != project_id:
        raise NotFoundError(message=f"Collection '{collection_id}' not found.")
    updated = await repo.update(collection_id, data)
    if not updated:
        raise ConflictError(message="Revision conflict — the collection was modified by another client.")
    return CollectionResponse.model_validate(updated)


@router.post("/{collection_id}/duplicate", response_model=CollectionResponse, status_code=201)
async def duplicate_collection(
    project_id: str,
    collection_id: str,
    repo: CollectionRepository = Depends(_get_collection_repo),  # noqa: B008
) -> CollectionResponse:
    """Duplicate a collection and all its requests."""
    existing = await repo.get(collection_id)
    if not existing or existing.get("project_id") != project_id:
        raise NotFoundError(message=f"Collection '{collection_id}' not found.")
    new_col = await repo.duplicate(collection_id)
    if not new_col:
        raise NotFoundError(message=f"Collection '{collection_id}' not found.")
    return CollectionResponse.model_validate(
        {**new_col, "project_id": project_id}
    )


@router.delete("/{collection_id}", status_code=204)
async def delete_collection(
    project_id: str,
    collection_id: str,
    repo: CollectionRepository = Depends(_get_collection_repo),  # noqa: B008
) -> None:
    """Delete a collection."""
    existing = await repo.get(collection_id)
    if not existing or existing.get("project_id") != project_id:
        raise NotFoundError(message=f"Collection '{collection_id}' not found.")
    success = await repo.delete(collection_id)
    if not success:
        raise NotFoundError(message=f"Collection '{collection_id}' not found.")


# ── Collection tree (requests within a collection) ──────────────────────


@router.get("/{collection_id}/requests", response_model=PaginatedResponse)
async def list_collection_requests(
    project_id: str,
    collection_id: str,
    col_repo: CollectionRepository = Depends(_get_collection_repo),  # noqa: B008
    req_repo: RequestRepository = Depends(_get_request_repo),  # noqa: B008
) -> PaginatedResponse:
    """List all requests in a collection."""
    col = await col_repo.get(collection_id)
    if not col or col.get("project_id") != project_id:
        raise NotFoundError(message=f"Collection '{collection_id}' not found.")
    reqs = await req_repo.list_all(collection_id=collection_id)
    items = [_request_to_response(r) for r in reqs]
    return PaginatedResponse(items=items, total=len(items))


def _request_to_response(req: dict) -> dict:
    """Convert a raw request dict to a camelCase response dict."""
    import json
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
