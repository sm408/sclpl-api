"""Projects API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.models.project import DEFAULT_PROJECT_ID
from app.services.project_service import ProjectRepository
from app.web.deps import _get_project_repo
from app.web.dto import PaginatedResponse, ProjectCreate, ProjectResponse, ProjectUpdate
from app.web.errors import ConflictError, NotFoundError, ValidationError

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("", response_model=PaginatedResponse)
async def list_projects(
    repo: ProjectRepository = Depends(_get_project_repo),  # noqa: B008
) -> PaginatedResponse:
    """Return all projects."""
    projects = await repo.list_all()
    items = [
        ProjectResponse.model_validate(p).model_dump(by_alias=True) for p in projects
    ]
    return PaginatedResponse(items=items, total=len(items))


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    repo: ProjectRepository = Depends(_get_project_repo),  # noqa: B008
) -> ProjectResponse:
    """Create a new project."""
    if not body.name or not body.name.strip():
        raise ValidationError(
            message="Project name is required.",
            field_errors=[
                {"field": "name", "message": "Project name is required."}
            ],
        )
    project = await repo.create(name=body.name, description=body.description)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    repo: ProjectRepository = Depends(_get_project_repo),  # noqa: B008
) -> ProjectResponse:
    """Return a single project by ID."""
    project = await repo.get(project_id)
    if not project:
        raise NotFoundError(message=f"Project '{project_id}' not found.")
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    repo: ProjectRepository = Depends(_get_project_repo),  # noqa: B008
) -> ProjectResponse:
    """Update a project's name and/or description."""
    if project_id == DEFAULT_PROJECT_ID:
        raise ConflictError(message="The Default project cannot be modified.")
    data = body.model_dump(exclude_unset=True, by_alias=False)
    if not data:
        raise ValidationError(
            message="At least one field must be provided.",
            field_errors=[
                {"field": "body", "message": "At least one field must be provided."}
            ],
        )
    success = await repo.update(project_id, data)
    if not success:
        raise NotFoundError(message=f"Project '{project_id}' not found.")
    project = await repo.get(project_id)
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    repo: ProjectRepository = Depends(_get_project_repo),  # noqa: B008
) -> None:
    """Delete a project.  Cannot delete the Default project."""
    if project_id == DEFAULT_PROJECT_ID:
        raise ConflictError(message="The Default project cannot be deleted.")
    success = await repo.delete(project_id)
    if not success:
        raise NotFoundError(message=f"Project '{project_id}' not found.")
