"""Environments API routes.

Provides CRUD for environments, activation, and variable management.
Secret values are masked in all responses.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.services.environment_service import EnvironmentRepository
from app.web.deps import _get_environment_repo
from app.web.dto import (
    EnvironmentCreate,
    EnvironmentResponse,
    EnvironmentUpdate,
    PaginatedResponse,
    VariableCreate,
    VariableDto,
)
from app.web.errors import ConflictError, NotFoundError, ValidationError

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/environments",
    tags=["environments"],
)

_SECRET_MASK = "***"


def _mask_variable(var: dict) -> dict:
    """Mask secret values in a variable dict and strip DB-only fields."""
    result = {
        "key": var.get("key", ""),
        "value": _SECRET_MASK if var.get("is_secret") else var.get("value", ""),
        "scope": var.get("scope", "environment"),
        "is_secret": bool(var.get("is_secret", 0)),
        "enabled": bool(var.get("enabled", 1)),
    }
    return result


def _to_response(env: dict) -> dict:
    """Convert a raw environment dict to a camelCase response dict with masked secrets."""
    variables = [_mask_variable(v) for v in env.get("variables", [])]
    return EnvironmentResponse(
        id=env["id"],
        project_id=env.get("project_id", ""),
        name=env["name"],
        is_active=bool(env.get("is_active", 0)),
        variables=[VariableDto(**v) for v in variables],
        revision=env.get("revision", 1),
        created_at=env.get("created_at"),
        updated_at=env.get("updated_at"),
    ).model_dump(by_alias=True)


@router.get("", response_model=PaginatedResponse)
async def list_environments(
    project_id: str,
    repo: EnvironmentRepository = Depends(_get_environment_repo),  # noqa: B008
) -> PaginatedResponse:
    """List all environments for a project with masked secrets."""
    envs = await repo.list_all(project_id=project_id)
    items = [_to_response(e) for e in envs]
    return PaginatedResponse(items=items, total=len(items))


@router.post("", response_model=EnvironmentResponse, status_code=201)
async def create_environment(
    project_id: str,
    body: EnvironmentCreate,
    repo: EnvironmentRepository = Depends(_get_environment_repo),  # noqa: B008
) -> EnvironmentResponse:
    """Create a new environment."""
    if not body.name or not body.name.strip():
        raise ValidationError(
            message="Environment name is required.",
            field_errors=[{"field": "name", "message": "Environment name is required."}],
        )
    env = await repo.create(name=body.name, project_id=project_id)

    # Set initial variables if provided
    if body.variables:
        var_dicts = [v.model_dump() for v in body.variables]
        await repo.set_variables(env["id"], var_dicts)

    # Re-fetch with variables
    env = await repo.get(env["id"])
    return EnvironmentResponse.model_validate(_to_response(env))


@router.get("/active", response_model=EnvironmentResponse)
async def get_active_environment(
    project_id: str,
    repo: EnvironmentRepository = Depends(_get_environment_repo),  # noqa: B008
) -> EnvironmentResponse:
    """Get the currently active environment for the project."""
    env = await repo.get_active(project_id=project_id)
    if not env:
        raise NotFoundError(message="No active environment for this project.")
    return EnvironmentResponse.model_validate(_to_response(env))


@router.get("/{environment_id}", response_model=EnvironmentResponse)
async def get_environment(
    project_id: str,
    environment_id: str,
    repo: EnvironmentRepository = Depends(_get_environment_repo),  # noqa: B008
) -> EnvironmentResponse:
    """Get a single environment with masked secrets."""
    env = await repo.get(environment_id)
    if not env or env.get("project_id") != project_id:
        raise NotFoundError(message=f"Environment '{environment_id}' not found.")
    return EnvironmentResponse.model_validate(_to_response(env))


@router.patch("/{environment_id}", response_model=EnvironmentResponse)
async def update_environment(
    project_id: str,
    environment_id: str,
    body: EnvironmentUpdate,
    repo: EnvironmentRepository = Depends(_get_environment_repo),  # noqa: B008
) -> EnvironmentResponse:
    """Update an environment's name."""
    existing = await repo.get(environment_id)
    if not existing or existing.get("project_id") != project_id:
        raise NotFoundError(message=f"Environment '{environment_id}' not found.")
    data = body.model_dump(exclude_unset=True, by_alias=False)
    if not data:
        raise ValidationError(
            message="At least one field must be provided.",
            field_errors=[{"field": "body", "message": "At least one field must be provided."}],
        )
    updated = await repo.update(environment_id, data)
    if not updated:
        raise ConflictError(message="Revision conflict.")
    return EnvironmentResponse.model_validate(_to_response(updated))


@router.post("/{environment_id}/activate", response_model=EnvironmentResponse)
async def activate_environment(
    project_id: str,
    environment_id: str,
    repo: EnvironmentRepository = Depends(_get_environment_repo),  # noqa: B008
) -> EnvironmentResponse:
    """Activate an environment (deactivates all others in the project)."""
    existing = await repo.get(environment_id)
    if not existing or existing.get("project_id") != project_id:
        raise NotFoundError(message=f"Environment '{environment_id}' not found.")
    await repo.set_active(environment_id, project_id=project_id)
    env = await repo.get(environment_id)
    return EnvironmentResponse.model_validate(_to_response(env))


@router.delete("/{environment_id}", status_code=204)
async def delete_environment(
    project_id: str,
    environment_id: str,
    repo: EnvironmentRepository = Depends(_get_environment_repo),  # noqa: B008
) -> None:
    """Delete an environment."""
    existing = await repo.get(environment_id)
    if not existing or existing.get("project_id") != project_id:
        raise NotFoundError(message=f"Environment '{environment_id}' not found.")
    success = await repo.delete(environment_id)
    if not success:
        raise NotFoundError(message=f"Environment '{environment_id}' not found.")


# ── Variable management ─────────────────────────────────────────────────


@router.put("/{environment_id}/variables", response_model=EnvironmentResponse)
async def set_variables(
    project_id: str,
    environment_id: str,
    variables: list[VariableCreate],
    repo: EnvironmentRepository = Depends(_get_environment_repo),  # noqa: B008
) -> EnvironmentResponse:
    """Replace all variables for an environment."""
    existing = await repo.get(environment_id)
    if not existing or existing.get("project_id") != project_id:
        raise NotFoundError(message=f"Environment '{environment_id}' not found.")
    var_dicts = [v.model_dump() for v in variables]
    await repo.set_variables(environment_id, var_dicts)
    env = await repo.get(environment_id)
    return EnvironmentResponse.model_validate(_to_response(env))


@router.post("/{environment_id}/variables", response_model=EnvironmentResponse, status_code=201)
async def add_variable(
    project_id: str,
    environment_id: str,
    body: VariableCreate,
    repo: EnvironmentRepository = Depends(_get_environment_repo),  # noqa: B008
) -> EnvironmentResponse:
    """Add or update a single variable."""
    existing = await repo.get(environment_id)
    if not existing or existing.get("project_id") != project_id:
        raise NotFoundError(message=f"Environment '{environment_id}' not found.")
    await repo.set_variable(environment_id, body.key, body.value, is_secret=body.is_secret)
    env = await repo.get(environment_id)
    return EnvironmentResponse.model_validate(_to_response(env))


@router.delete("/{environment_id}/variables/{key}", status_code=204)
async def delete_variable(
    project_id: str,
    environment_id: str,
    key: str,
    repo: EnvironmentRepository = Depends(_get_environment_repo),  # noqa: B008
) -> None:
    """Delete a variable from an environment."""
    existing = await repo.get(environment_id)
    if not existing or existing.get("project_id") != project_id:
        raise NotFoundError(message=f"Environment '{environment_id}' not found.")
    success = await repo.delete_variable(environment_id, key)
    if not success:
        raise NotFoundError(message=f"Variable '{key}' not found.")
