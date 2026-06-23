"""Function API routes.

Provides CRUD for Python transformation functions, AST validation,
fixture execution, trust acknowledgement, and file tree listing.
All operations are scoped to a project.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.services.function_service import FunctionService, TrustRequiredError
from app.services.project_service import ProjectRepository
from app.web.converters import (
    ast_result_to_response,
    fixture_result_to_response,
    function_list_item_to_response,
    function_to_response,
)
from app.web.dto import (
    AstValidationResult,
    FixtureResult,
    FixtureRunRequest,
    FunctionCreate,
    FunctionResponse,
    FunctionListItem,
    FunctionUpdate,
    PaginatedResponse,
    TrustAckRequest,
    TrustAckResponse,
)
from app.web.errors import BadRequestError, NotFoundError, ValidationError

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/functions",
    tags=["functions"],
)


async def _get_function_service(
    project_id: str,
    request: Request,
) -> FunctionService:
    """Build a FunctionService scoped to the project root."""
    project_repo: ProjectRepository = request.app.state.services.projects
    project = await project_repo.get(project_id)
    if not project:
        raise NotFoundError(message=f"Project '{project_id}' not found.")

    from pathlib import Path
    root = Path(project.root_path) if project.root_path else Path("data") / "projects" / project_id
    if not root.is_absolute():
        root = Path.cwd() / root

    return FunctionService(project_id, root)


# ── File tree ────────────────────────────────────────────────────────────


@router.get("/tree")
async def list_function_tree(
    project_id: str,
    request: Request,
) -> dict:
    """List the function file tree for a project."""
    svc = await _get_function_service(project_id, request)
    tree = svc.list_tree()
    return {"tree": tree}


# ── List ─────────────────────────────────────────────────────────────────


@router.get("", response_model=PaginatedResponse)
async def list_functions(
    project_id: str,
    request: Request,
) -> PaginatedResponse:
    """List all functions for a project."""
    svc = await _get_function_service(project_id, request)
    functions = svc.list_functions()
    items = [function_list_item_to_response(f) for f in functions]
    return PaginatedResponse(items=items, total=len(items))


# ── Get ──────────────────────────────────────────────────────────────────


@router.get("/{path:path}", response_model=FunctionResponse)
async def get_function(
    project_id: str,
    path: str,
    request: Request,
) -> dict:
    """Get a single function with content and metadata."""
    svc = await _get_function_service(project_id, request)
    try:
        data = svc.get_function(path)
    except Exception as exc:
        raise NotFoundError(message=f"Function '{path}' not found.")
    return function_to_response(data)


# ── Create / Save ────────────────────────────────────────────────────────


@router.post("", response_model=FunctionResponse, status_code=201)
async def create_function(
    project_id: str,
    body: FunctionCreate,
    request: Request,
) -> dict:
    """Create a new function file."""
    if not body.name or not body.name.strip():
        raise ValidationError(
            message="Function name is required.",
            field_errors=[{"field": "name", "message": "Function name is required."}],
        )

    svc = await _get_function_service(project_id, request)

    # Build path from name
    path = body.name if body.name.endswith(".py") else f"{body.name}.py"

    # Add docstring metadata if source doesn't have one
    source = body.source
    if body.description and not source.lstrip().startswith('"""'):
        source = f'"""\n@name: {body.name}\n@description: {body.description}\n"""\n\n{source}'

    try:
        data = svc.save_function(path, source)
    except ValidationError:
        raise
    except Exception as exc:
        raise BadRequestError(message=f"Failed to create function: {exc}")

    return function_to_response(data)


# ── Update ───────────────────────────────────────────────────────────────


@router.patch("/{path:path}", response_model=FunctionResponse)
async def update_function(
    project_id: str,
    path: str,
    body: FunctionUpdate,
    request: Request,
) -> dict:
    """Update a function's source content."""
    svc = await _get_function_service(project_id, request)

    # Read current to verify exists
    try:
        current = svc.get_function(path)
    except Exception:
        raise NotFoundError(message=f"Function '{path}' not found.")

    if body.source is not None:
        try:
            data = svc.save_function(path, body.source, expected_hash=body.expected_hash)
        except ValidationError:
            raise
        except Exception as exc:
            raise BadRequestError(message=f"Failed to save function: {exc}")
    else:
        data = current

    return function_to_response(data)


# ── Delete ───────────────────────────────────────────────────────────────


@router.delete("/{path:path}", status_code=204)
async def delete_function(
    project_id: str,
    path: str,
    request: Request,
) -> None:
    """Delete a function file."""
    svc = await _get_function_service(project_id, request)
    success = svc.delete_function(path)
    if not success:
        raise NotFoundError(message=f"Function '{path}' not found.")


# ── Validate ─────────────────────────────────────────────────────────────


@router.post("/validate")
async def validate_function_source(
    project_id: str,
    body: dict[str, str],
    request: Request,
) -> dict:
    """Validate Python source code without executing it."""
    source = body.get("source", "")
    svc = await _get_function_service(project_id, request)
    result = svc.validate_source(source)
    return ast_result_to_response(result)


# ── Fixture execution ────────────────────────────────────────────────────


@router.post("/{path:path}/run", response_model=FixtureResult)
async def run_function_fixture(
    project_id: str,
    path: str,
    body: FixtureRunRequest,
    request: Request,
) -> dict:
    """Execute a function with fixture input.

    Requires trust acknowledgement unless ``trusted: true`` is passed.
    """
    svc = await _get_function_service(project_id, request)

    try:
        result = await svc.run_fixture(
            path,
            body.fixture_input,
            trusted=body.trusted,
        )
    except TrustRequiredError as exc:
        return JSONResponse(
            status_code=428,
            content={
                "error": {
                    "code": "TRUST_REQUIRED",
                    "message": str(exc),
                    "fieldErrors": [
                        {"field": "path", "message": exc.path},
                        {"field": "hash", "message": exc.content_hash},
                    ],
                    "correlationId": "",
                }
            },
        )
    except Exception as exc:
        raise BadRequestError(message=f"Fixture execution failed: {exc}")

    return fixture_result_to_response(result)


# ── Trust management ─────────────────────────────────────────────────────


@router.post("/{path:path}/trust", response_model=TrustAckResponse)
async def acknowledge_trust(
    project_id: str,
    path: str,
    body: TrustAckRequest,
    request: Request,
) -> dict:
    """Acknowledge trust for executing a function."""
    svc = await _get_function_service(project_id, request)
    result = svc.acknowledge_trust(path, body.content_hash)
    return TrustAckResponse(
        path=result["path"],
        hash=result["hash"],
        trusted=result["trusted"],
    ).model_dump(by_alias=True)


@router.delete("/{path:path}/trust", status_code=204)
async def revoke_trust(
    project_id: str,
    path: str,
    request: Request,
) -> None:
    """Revoke trust for a function."""
    svc = await _get_function_service(project_id, request)
    svc.revoke_trust(path)
