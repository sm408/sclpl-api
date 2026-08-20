"""Workflow API routes.

Provides CRUD for workflow documents, SCLPLL parse/preview/apply,
version management, preflight validation, and execution snapshots.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.core.models.workflow_document import GraphLayout, RevisionConflict
from app.services.workflow_service import WorkflowRepository
from app.web.converters import (
    conflict_to_response,
    parse_result_to_response,
    preflight_to_response,
    preview_to_response,
    version_to_response,
    workflow_to_response,
)
from app.web.deps import _get_workflow_repo
from app.web.dto import (
    GenerateSclpllResponse,
    PaginatedResponse,
    SclpllApplyRequest,
    VersionCompareRequest,
    VersionCreateRequest,
    VersionRestoreRequest,
    WorkflowCreate,
    WorkflowResponse,
    WorkflowUpdate,
)
from app.web.errors import ConflictError, NotFoundError, ValidationError

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/workflows",
    tags=["workflows"],
)


# ── CRUD ──────────────────────────────────────────────────────────────


@router.get("", response_model=PaginatedResponse)
async def list_workflows(
    project_id: str,
    repo: WorkflowRepository = Depends(_get_workflow_repo),  # noqa: B008
) -> PaginatedResponse:
    """List all workflows for a project."""
    docs = await repo.list_all(project_id=project_id)
    items = [workflow_to_response(d) for d in docs]
    return PaginatedResponse(items=items, total=len(items))


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    project_id: str,
    body: WorkflowCreate,
    repo: WorkflowRepository = Depends(_get_workflow_repo),  # noqa: B008
) -> dict:
    """Create a new workflow document."""
    if not body.name or not body.name.strip():
        raise ValidationError(
            message="Workflow name is required.",
            field_errors=[{"field": "name", "message": "Workflow name is required."}],
        )
    layout = None
    if body.layout:
        layout = GraphLayout(
            nodes=body.layout.nodes,
            viewport=body.layout.viewport,
        )
    doc = await repo.create(
        name=body.name,
        project_id=project_id,
        description=body.description,
        definition=body.definition,
        layout=layout,
        sclpll_source=body.sclpll_source,
    )
    return workflow_to_response(doc)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    project_id: str,
    workflow_id: str,
    repo: WorkflowRepository = Depends(_get_workflow_repo),  # noqa: B008
) -> dict:
    """Get a single workflow document."""
    doc = await repo.get(workflow_id)
    if not doc or doc.project_id != project_id:
        raise NotFoundError(message=f"Workflow '{workflow_id}' not found.")
    return workflow_to_response(doc)


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    project_id: str,
    workflow_id: str,
    body: WorkflowUpdate,
    repo: WorkflowRepository = Depends(_get_workflow_repo),  # noqa: B008
) -> dict:
    """Update a workflow document."""
    existing = await repo.get(workflow_id)
    if not existing or existing.project_id != project_id:
        raise NotFoundError(message=f"Workflow '{workflow_id}' not found.")

    data: dict[str, Any] = {}
    if body.name is not None:
        data["name"] = body.name
    if body.description is not None:
        data["description"] = body.description
    if body.definition is not None:
        data["definition"] = body.definition
    if body.layout is not None:
        data["layout"] = GraphLayout(
            nodes=body.layout.nodes,
            viewport=body.layout.viewport,
        )
    if body.sclpll_source is not None:
        data["sclpll_source"] = body.sclpll_source

    if not data:
        raise ValidationError(
            message="At least one field must be provided.",
            field_errors=[{"field": "body", "message": "At least one field must be provided."}],
        )

    result = await repo.update(workflow_id, data, revision=body.revision)
    if result is None:
        raise NotFoundError(message=f"Workflow '{workflow_id}' not found.")
    if isinstance(result, RevisionConflict):
        raise ConflictError(
            message="Revision conflict — the workflow was modified by another client.",
            field_errors=[conflict_to_response(result)],
        )
    return workflow_to_response(result)


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    project_id: str,
    workflow_id: str,
    repo: WorkflowRepository = Depends(_get_workflow_repo),  # noqa: B008
) -> None:
    """Delete a workflow and its versions."""
    existing = await repo.get(workflow_id)
    if not existing or existing.project_id != project_id:
        raise NotFoundError(message=f"Workflow '{workflow_id}' not found.")
    success = await repo.delete(workflow_id)
    if not success:
        raise NotFoundError(message=f"Workflow '{workflow_id}' not found.")


@router.post("/{workflow_id}/duplicate", response_model=WorkflowResponse, status_code=201)
async def duplicate_workflow(
    project_id: str,
    workflow_id: str,
    repo: WorkflowRepository = Depends(_get_workflow_repo),  # noqa: B008
) -> dict:
    """Duplicate a workflow document."""
    existing = await repo.get(workflow_id)
    if not existing or existing.project_id != project_id:
        raise NotFoundError(message=f"Workflow '{workflow_id}' not found.")
    new_doc = await repo.duplicate(workflow_id)
    if not new_doc:
        raise NotFoundError(message=f"Workflow '{workflow_id}' not found.")
    return workflow_to_response(new_doc)


# ── SCLPLL Operations ─────────────────────────────────────────────────


@router.post("/sclpll/parse")
async def parse_sclpll(
    project_id: str,
    body: SclpllApplyRequest,
    repo: WorkflowRepository = Depends(_get_workflow_repo),  # noqa: B008
) -> dict:
    """Parse SCLPLL source and return structured result with diagnostics."""
    result = repo.parse_sclpll(body.source)
    return parse_result_to_response(result)


@router.post("/sclpll/preview")
async def preview_sclpll(
    project_id: str,
    body: SclpllApplyRequest,
    workflow_id: str | None = None,
    repo: WorkflowRepository = Depends(_get_workflow_repo),  # noqa: B008
) -> dict:
    """Preview what would change when applying SCLPLL source."""
    current_def = None
    if workflow_id:
        doc = await repo.get(workflow_id)
        if doc:
            current_def = doc.definition
    result = repo.preview_sclpll(body.source, current_definition=current_def)
    return preview_to_response(result)


@router.post("/{workflow_id}/sclpll/apply", response_model=WorkflowResponse)
async def apply_sclpll(
    project_id: str,
    workflow_id: str,
    body: SclpllApplyRequest,
    repo: WorkflowRepository = Depends(_get_workflow_repo),  # noqa: B008
) -> dict:
    """Parse SCLPLL source and apply it to the workflow."""
    existing = await repo.get(workflow_id)
    if not existing or existing.project_id != project_id:
        raise NotFoundError(message=f"Workflow '{workflow_id}' not found.")

    try:
        result = await repo.apply_sclpll(
            workflow_id, body.source, revision=body.revision,
        )
    except ValueError as exc:
        raise ValidationError(message=str(exc))

    if result is None:
        raise NotFoundError(message=f"Workflow '{workflow_id}' not found.")
    if isinstance(result, RevisionConflict):
        raise ConflictError(
            message="Revision conflict — the workflow was modified by another client.",
            field_errors=[conflict_to_response(result)],
        )
    return workflow_to_response(result)


@router.post("/{workflow_id}/sclpll/generate", response_model=GenerateSclpllResponse)
async def generate_sclpll(
    project_id: str,
    workflow_id: str,
    repo: WorkflowRepository = Depends(_get_workflow_repo),  # noqa: B008
) -> dict:
    """Generate SCLPLL from the current workflow definition."""
    doc = await repo.get(workflow_id)
    if not doc or doc.project_id != project_id:
        raise NotFoundError(message=f"Workflow '{workflow_id}' not found.")
    source = repo.generate_sclpll(doc.definition)
    return GenerateSclpllResponse(sclpll_source=source).model_dump(by_alias=True)


# ── Preflight Validation ──────────────────────────────────────────────


@router.post("/{workflow_id}/validate")
async def validate_workflow(
    project_id: str,
    workflow_id: str,
    repo: WorkflowRepository = Depends(_get_workflow_repo),  # noqa: B008
) -> dict:
    """Run preflight validation on a workflow."""
    doc = await repo.get(workflow_id)
    if not doc or doc.project_id != project_id:
        raise NotFoundError(message=f"Workflow '{workflow_id}' not found.")
    result = repo.validate_preflight(doc.definition)
    return preflight_to_response(result)


# ── Versions ──────────────────────────────────────────────────────────


@router.get("/{workflow_id}/versions")
async def list_versions(
    project_id: str,
    workflow_id: str,
    repo: WorkflowRepository = Depends(_get_workflow_repo),  # noqa: B008
) -> PaginatedResponse:
    """List all versions of a workflow."""
    existing = await repo.get(workflow_id)
    if not existing or existing.project_id != project_id:
        raise NotFoundError(message=f"Workflow '{workflow_id}' not found.")
    versions = await repo.list_versions(workflow_id)
    items = [version_to_response(v) for v in versions]
    return PaginatedResponse(items=items, total=len(items))


@router.post("/{workflow_id}/versions", status_code=201)
async def save_version(
    project_id: str,
    workflow_id: str,
    body: VersionCreateRequest,
    repo: WorkflowRepository = Depends(_get_workflow_repo),  # noqa: B008
) -> dict:
    """Save an immutable version snapshot."""
    existing = await repo.get(workflow_id)
    if not existing or existing.project_id != project_id:
        raise NotFoundError(message=f"Workflow '{workflow_id}' not found.")
    ver = await repo.save_version(
        workflow_id,
        description=body.description,
        author=body.author,
        metadata=body.metadata,
    )
    if not ver:
        raise NotFoundError(message=f"Workflow '{workflow_id}' not found.")
    return version_to_response(ver)


@router.get("/{workflow_id}/versions/{version}")
async def get_version(
    project_id: str,
    workflow_id: str,
    version: int,
    repo: WorkflowRepository = Depends(_get_workflow_repo),  # noqa: B008
) -> dict:
    """Get a specific version of a workflow."""
    existing = await repo.get(workflow_id)
    if not existing or existing.project_id != project_id:
        raise NotFoundError(message=f"Workflow '{workflow_id}' not found.")
    ver = await repo.get_version(workflow_id, version)
    if not ver:
        raise NotFoundError(message=f"Version {version} not found for workflow '{workflow_id}'.")
    return version_to_response(ver)


@router.post("/{workflow_id}/versions/restore", response_model=WorkflowResponse)
async def restore_version(
    project_id: str,
    workflow_id: str,
    body: VersionRestoreRequest,
    repo: WorkflowRepository = Depends(_get_workflow_repo),  # noqa: B008
) -> dict:
    """Restore a workflow to a previous version."""
    existing = await repo.get(workflow_id)
    if not existing or existing.project_id != project_id:
        raise NotFoundError(message=f"Workflow '{workflow_id}' not found.")
    doc = await repo.restore_version(workflow_id, body.version)
    if not doc:
        raise NotFoundError(
            message=f"Version {body.version} not found for workflow '{workflow_id}'."
        )
    return workflow_to_response(doc)


@router.post("/{workflow_id}/versions/compare")
async def compare_versions(
    project_id: str,
    workflow_id: str,
    body: VersionCompareRequest,
    repo: WorkflowRepository = Depends(_get_workflow_repo),  # noqa: B008
) -> dict:
    """Compare two versions and return the structural diff."""
    existing = await repo.get(workflow_id)
    if not existing or existing.project_id != project_id:
        raise NotFoundError(message=f"Workflow '{workflow_id}' not found.")
    diff = await repo.compare_versions(workflow_id, body.version_a, body.version_b)
    if diff is None:
        raise NotFoundError(
            message=f"Could not compare versions {body.version_a} and {body.version_b}."
        )
    from app.web.converters import _to_diff_dto
    return {"diff": [_to_diff_dto(d) for d in diff]}
