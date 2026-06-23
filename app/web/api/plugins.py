"""Plugin API routes.

Provides plugin discovery, detail, scaffold, enable/disable, reload,
manifest editing, diagnostics, and export.  All operations are scoped
to a project.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse

from app.services.plugin_service import PluginService
from app.services.project_service import ProjectRepository
from app.web.converters import (
    function_to_response,
    plugin_diagnostics_to_response,
    plugin_to_response,
)
from app.web.dto import (
    PaginatedResponse,
    PluginDiagnostics,
    PluginFileWrite,
    PluginManifestUpdate,
    PluginResponse,
    PluginScaffoldRequest,
)
from app.web.errors import BadRequestError, NotFoundError, ValidationError

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/plugins",
    tags=["plugins"],
)


async def _get_plugin_service(
    project_id: str,
    request: Request,
) -> PluginService:
    """Build a PluginService scoped to the project root."""
    project_repo: ProjectRepository = request.app.state.services.projects
    project = await project_repo.get(project_id)
    if not project:
        raise NotFoundError(message=f"Project '{project_id}' not found.")

    root = Path(project.root_path) if project.root_path else Path("data") / "projects" / project_id
    if not root.is_absolute():
        root = Path.cwd() / root

    return PluginService(project_id, root)


# ── List ─────────────────────────────────────────────────────────────────


@router.get("", response_model=PaginatedResponse)
async def list_plugins(
    project_id: str,
    request: Request,
) -> PaginatedResponse:
    """List all discovered plugins for a project."""
    svc = await _get_plugin_service(project_id, request)
    plugins = svc.list_plugins()
    items = [plugin_to_response(p) for p in plugins]
    return PaginatedResponse(items=items, total=len(items))


# ── Get ──────────────────────────────────────────────────────────────────


@router.get("/{name}", response_model=PluginResponse)
async def get_plugin(
    project_id: str,
    name: str,
    request: Request,
) -> dict:
    """Get a single plugin with manifest and metadata."""
    svc = await _get_plugin_service(project_id, request)
    try:
        data = svc.get_plugin(name)
    except NotFoundError:
        raise
    except Exception as exc:
        raise NotFoundError(message=f"Plugin '{name}' not found.")
    return plugin_to_response(data)


# ── Scaffold ─────────────────────────────────────────────────────────────


@router.post("", response_model=PluginResponse, status_code=201)
async def scaffold_plugin(
    project_id: str,
    body: PluginScaffoldRequest,
    request: Request,
) -> dict:
    """Create a new plugin scaffold."""
    if not body.name or not body.name.strip():
        raise ValidationError(
            message="Plugin name is required.",
            field_errors=[{"field": "name", "message": "Plugin name is required."}],
        )

    svc = await _get_plugin_service(project_id, request)
    try:
        data = svc.scaffold_plugin(body.name, body.description)
    except BadRequestError:
        raise
    except Exception as exc:
        raise BadRequestError(message=f"Failed to scaffold plugin: {exc}")

    return plugin_to_response(data)


# ── Enable ───────────────────────────────────────────────────────────────


@router.post("/{name}/enable", response_model=PluginResponse)
async def enable_plugin(
    project_id: str,
    name: str,
    request: Request,
) -> dict:
    """Load (enable) a plugin."""
    svc = await _get_plugin_service(project_id, request)
    try:
        data = svc.enable_plugin(name)
    except NotFoundError:
        raise
    except Exception as exc:
        raise BadRequestError(message=str(exc))
    return plugin_to_response(data)


# ── Disable ──────────────────────────────────────────────────────────────


@router.post("/{name}/disable", response_model=PluginResponse)
async def disable_plugin(
    project_id: str,
    name: str,
    request: Request,
) -> dict:
    """Unload (disable) a plugin."""
    svc = await _get_plugin_service(project_id, request)
    try:
        data = svc.disable_plugin(name)
    except NotFoundError:
        raise
    except Exception as exc:
        raise BadRequestError(message=str(exc))
    return plugin_to_response(data)


# ── Reload ───────────────────────────────────────────────────────────────


@router.post("/reload")
async def reload_plugins(
    project_id: str,
    request: Request,
) -> PaginatedResponse:
    """Re-scan and reload all plugins."""
    svc = await _get_plugin_service(project_id, request)
    plugins = svc.reload()
    items = [plugin_to_response(p) for p in plugins]
    return PaginatedResponse(items=items, total=len(items))


# ── Manifest ─────────────────────────────────────────────────────────────


@router.get("/{name}/manifest")
async def get_manifest(
    project_id: str,
    name: str,
    request: Request,
) -> dict:
    """Get the raw plugin.json manifest."""
    svc = await _get_plugin_service(project_id, request)
    data = svc.get_plugin(name)
    manifest = data.get("manifest")
    if manifest is None:
        raise NotFoundError(message=f"Plugin manifest not found for '{name}'.")
    return manifest


@router.patch("/{name}/manifest")
async def update_manifest(
    project_id: str,
    name: str,
    body: PluginManifestUpdate,
    request: Request,
) -> dict:
    """Update the plugin.json manifest."""
    svc = await _get_plugin_service(project_id, request)
    try:
        data = svc.update_manifest(name, body.data)
    except NotFoundError:
        raise
    except Exception as exc:
        raise BadRequestError(message=f"Failed to update manifest: {exc}")
    return plugin_to_response(data)


# ── File tree ────────────────────────────────────────────────────────────


@router.get("/{name}/tree")
async def get_plugin_tree(
    project_id: str,
    name: str,
    request: Request,
) -> dict:
    """Get the file tree for a plugin."""
    svc = await _get_plugin_service(project_id, request)
    try:
        tree = svc.get_plugin_tree(name)
    except NotFoundError:
        raise
    except Exception as exc:
        raise BadRequestError(message=f"Failed to list plugin tree: {exc}")
    return {"tree": tree}


# ── Plugin file read/write ───────────────────────────────────────────────


@router.get("/{name}/files/{path:path}")
async def read_plugin_file(
    project_id: str,
    name: str,
    path: str,
    request: Request,
) -> dict:
    """Read a file within a plugin directory."""
    svc = await _get_plugin_service(project_id, request)
    try:
        return svc.read_plugin_file(name, path)
    except NotFoundError:
        raise
    except Exception as exc:
        raise BadRequestError(message=f"Failed to read file: {exc}")


@router.put("/{name}/files/{path:path}")
async def write_plugin_file(
    project_id: str,
    name: str,
    path: str,
    body: PluginFileWrite,
    request: Request,
) -> dict:
    """Write a file within a plugin directory."""
    svc = await _get_plugin_service(project_id, request)
    try:
        return svc.write_plugin_file(
            name, path, body.content, expected_hash=body.expected_hash,
        )
    except NotFoundError:
        raise
    except Exception as exc:
        raise BadRequestError(message=f"Failed to write file: {exc}")


# ── Diagnostics ──────────────────────────────────────────────────────────


@router.get("/{name}/diagnostics", response_model=PluginDiagnostics)
async def get_diagnostics(
    project_id: str,
    name: str,
    request: Request,
) -> dict:
    """Get plugin diagnostics with secrets excluded.

    Returns variable names but NOT values to protect secret content.
    """
    svc = await _get_plugin_service(project_id, request)
    try:
        data = svc.get_diagnostics(name)
    except NotFoundError:
        raise
    except Exception as exc:
        raise BadRequestError(message=f"Failed to get diagnostics: {exc}")
    return plugin_diagnostics_to_response(data)


# ── Export ───────────────────────────────────────────────────────────────


@router.get("/{name}/export")
async def export_plugin(
    project_id: str,
    name: str,
    request: Request,
    background_tasks: BackgroundTasks,
) -> FileResponse:
    """Export a plugin as a zip archive."""
    svc = await _get_plugin_service(project_id, request)
    try:
        zip_path = svc.export_plugin(name)
    except NotFoundError:
        raise
    except Exception as exc:
        raise BadRequestError(message=f"Failed to export plugin: {exc}")

    background_tasks.add_task(_cleanup_temp, zip_path)

    return FileResponse(
        path=str(zip_path),
        filename=f"{name}.zip",
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}.zip"'},
    )


def _cleanup_temp(path: Path) -> None:
    """Remove a temporary file, ignoring errors."""
    try:
        os.unlink(path)
    except OSError:
        pass
