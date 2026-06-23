"""Plugin service with scaffold, enable/disable, reload, and export.

Wraps FilesystemPluginRegistry for project-root-aware discovery and
adds file-based operations (scaffold, edit manifest, export) through
FileService.
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from pathlib import Path

from app.core.engine.plugin_registry import FilesystemPluginRegistry
from app.core.models.plugin import PluginInfo, PluginStatus
from app.services.file_service import (
    PLUGIN_ALLOWED_EXTENSIONS,
    FileService,
    create_plugin_file_service,
)
from app.web.errors import BadRequestError, NotFoundError

logger = logging.getLogger(__name__)


class PluginService:
    """Service for managing plugins within a project.

    Parameters
    ----------
    project_id:
        The project identifier.
    project_root:
        Root directory of the project (plugins are under ``plugins/``).
    """

    def __init__(self, project_id: str, project_root: str | Path) -> None:
        self._project_id = project_id
        self._project_root = Path(project_root)
        plugin_dir = self._project_root / "plugins"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        self._registry = FilesystemPluginRegistry(str(plugin_dir))
        self._file_service = create_plugin_file_service(project_root)

    # ── Discovery ───────────────────────────────────────────────────────

    def list_plugins(self) -> list[dict]:
        """List all discovered plugins with their status."""
        plugins = self._registry.discover()
        return [self._plugin_to_dict(p) for p in plugins]

    def get_plugin(self, name: str) -> dict:
        """Get a single plugin by name."""
        plugin = self._registry.get_plugin(name)
        if plugin is None:
            raise NotFoundError(message=f"Plugin '{name}' not found.")

        # Read plugin.json manifest if available
        manifest_data = self._read_manifest(name)

        result = self._plugin_to_dict(plugin)
        result["manifest"] = manifest_data
        return result

    def get_plugin_tree(self, name: str) -> list[dict]:
        """Get the file tree for a plugin directory."""
        plugin_dir = Path(self._project_root) / "plugins" / name
        if not plugin_dir.exists():
            raise NotFoundError(message=f"Plugin '{name}' not found.")
        fs = FileService(plugin_dir, allowed_extensions=PLUGIN_ALLOWED_EXTENSIONS)
        return fs.list_tree("")

    def read_plugin_file(self, name: str, relative: str) -> dict:
        """Read a file within a plugin directory."""
        plugin_dir = Path(self._project_root) / "plugins" / name
        if not plugin_dir.exists():
            raise NotFoundError(message=f"Plugin '{name}' not found.")
        fs = FileService(plugin_dir, allowed_extensions=PLUGIN_ALLOWED_EXTENSIONS)
        return fs.read_file(relative)

    def write_plugin_file(
        self,
        name: str,
        relative: str,
        content: str,
        *,
        expected_hash: str | None = None,
    ) -> dict:
        """Write a file within a plugin directory."""
        plugin_dir = Path(self._project_root) / "plugins" / name
        if not plugin_dir.exists():
            raise NotFoundError(message=f"Plugin '{name}' not found.")
        fs = FileService(plugin_dir, allowed_extensions=PLUGIN_ALLOWED_EXTENSIONS)
        return fs.write_file(relative, content, expected_hash=expected_hash)

    # ── Scaffold ────────────────────────────────────────────────────────

    def scaffold_plugin(self, name: str, description: str = "") -> dict:
        """Create a new plugin scaffold.

        Creates the plugin directory with ``plugin.json``, functions
        subdirectory, and an example function.
        """
        plugin_dir = Path(self._project_root) / "plugins" / name
        if plugin_dir.exists():
            raise BadRequestError(
                message=f"Plugin '{name}' already exists.",
                field_errors=[{"field": "name", "message": "Plugin name must be unique."}],
            )

        # Use registry scaffold
        self._registry.scaffold_plugin(name)

        # Update description if provided
        if description:
            manifest_path = plugin_dir / "plugin.json"
            if manifest_path.exists():
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                data["description"] = description
                manifest_path.write_text(
                    json.dumps(data, indent=2), encoding="utf-8",
                )

        return self.get_plugin(name)

    # ── Enable/Disable ──────────────────────────────────────────────────

    def enable_plugin(self, name: str) -> dict:
        """Load (enable) a plugin."""
        plugin = self._registry.get_plugin(name)
        if plugin is None:
            raise NotFoundError(message=f"Plugin '{name}' not found.")

        try:
            loaded = self._registry.load(name)
            return self._plugin_to_dict(loaded)
        except Exception as exc:
            raise BadRequestError(
                message=f"Failed to load plugin '{name}': {exc}",
                field_errors=[{"field": "name", "message": str(exc)}],
            )

    def disable_plugin(self, name: str) -> dict:
        """Unload (disable) a plugin."""
        plugin = self._registry.get_plugin(name)
        if plugin is None:
            raise NotFoundError(message=f"Plugin '{name}' not found.")

        self._registry.unload(name)
        plugin.status = PluginStatus.DISCOVERED
        return self._plugin_to_dict(plugin)

    # ── Reload ──────────────────────────────────────────────────────────

    def reload(self) -> list[dict]:
        """Re-scan and reload all plugins."""
        plugins = self._registry.reload()
        return [self._plugin_to_dict(p) for p in plugins]

    # ── Export ──────────────────────────────────────────────────────────

    def export_plugin(self, name: str) -> Path:
        """Export a plugin directory as a zip archive.

        Returns the path to the temporary zip file. Caller is
        responsible for cleaning up.
        """
        plugin_dir = Path(self._project_root) / "plugins" / name
        if not plugin_dir.exists():
            raise NotFoundError(message=f"Plugin '{name}' not found.")

        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        tmp_path = Path(tmp.name)
        tmp.close()

        shutil.make_archive(str(tmp_path.with_suffix("")), "zip", str(plugin_dir))
        return tmp_path.with_suffix(".zip")

    # ── Manifest editing ────────────────────────────────────────────────

    def update_manifest(self, name: str, data: dict) -> dict:
        """Update the plugin.json manifest for a plugin."""
        plugin_dir = Path(self._project_root) / "plugins" / name
        if not plugin_dir.exists():
            raise NotFoundError(message=f"Plugin '{name}' not found.")

        manifest_path = plugin_dir / "plugin.json"
        if not manifest_path.exists():
            raise NotFoundError(message=f"Plugin manifest not found for '{name}'.")

        current = json.loads(manifest_path.read_text(encoding="utf-8"))

        # Merge allowed fields
        allowed_keys = {
            "name", "version", "description", "author", "category",
            "functions", "workflows", "hooks", "variables", "dependencies",
        }
        for key in allowed_keys:
            if key in data:
                current[key] = data[key]

        manifest_path.write_text(json.dumps(current, indent=2), encoding="utf-8")

        return self.get_plugin(name)

    # ── Diagnostics (secret-safe) ───────────────────────────────────────

    def get_diagnostics(self, name: str) -> dict:
        """Return plugin diagnostics with secrets excluded.

        Returns status, function count, error details, and variable
        names (but NOT values, to protect secrets).
        """
        plugin = self._registry.get_plugin(name)
        if plugin is None:
            raise NotFoundError(message=f"Plugin '{name}' not found.")

        # Variable names only, no values
        variable_names = list(plugin.manifest.variables.keys())

        return {
            "name": name,
            "status": plugin.status.value if hasattr(plugin.status, "value") else plugin.status,
            "functionCount": len(plugin.functions),
            "workflowCount": len(plugin.workflows),
            "variableNames": variable_names,
            "error": plugin.error,
            "dependencies": plugin.manifest.dependencies,
        }

    # ── Internal helpers ────────────────────────────────────────────────

    def _plugin_to_dict(self, plugin: PluginInfo) -> dict:
        """Convert a PluginInfo to a response dict."""
        status_val = plugin.status.value if hasattr(plugin.status, "value") else plugin.status
        return {
            "id": plugin.manifest.name,
            "name": plugin.manifest.name,
            "version": plugin.manifest.version,
            "description": plugin.manifest.description,
            "author": plugin.manifest.author,
            "category": plugin.manifest.category,
            "status": status_val,
            "functionCount": len(plugin.functions),
            "workflowCount": len(plugin.workflows),
            "variableNames": list(plugin.manifest.variables.keys()),
            "error": plugin.error,
            "dependencies": plugin.manifest.dependencies,
        }

    def _read_manifest(self, name: str) -> dict | None:
        """Read the raw plugin.json if it exists."""
        manifest_path = Path(self._project_root) / "plugins" / name / "plugin.json"
        if not manifest_path.exists():
            return None
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return None
