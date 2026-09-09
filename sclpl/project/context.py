"""Strict, portable project-manifest loading."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sclpl.errors import ValidationError

MANIFEST = "sclpl.toml"
SELECTION = ".sclpl/environment"
SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ProjectContext:
    """Resolved non-secret project configuration, with its selection provenance."""

    root: Path
    manifest_path: Path
    manifest: dict[str, Any]
    environment: str
    environment_source: str

    @property
    def settings(self) -> dict[str, Any]:
        project = _table(self.manifest, "project")
        base = _table(project, "settings")
        environments = _table(self.manifest, "environments")
        overlay = _table(environments.get(self.environment, {}), "settings")
        return {**base, **overlay}

    @property
    def plugin_settings(self) -> dict[str, dict[str, Any]]:
        """Opaque, non-secret settings merged for the selected environment."""
        base = _table(self.manifest, "plugins")
        environments = _table(self.manifest, "environments")
        overlay = _table(_table(environments.get(self.environment, {}), "plugins"), "")
        names = set(base) | set(overlay)
        return {name: _merge_tables(_table(base, name), _table(overlay, name)) for name in names}

    @property
    def workflow_dirs(self) -> list[Path]:
        paths = _table(self.manifest, "workflows").get("paths", ["workflows"])
        if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
            raise ValidationError(
                "workflows.paths must be an array of paths", where=str(self.manifest_path)
            )
        return [self.resolve_path(item) for item in paths]

    @property
    def test_dirs(self) -> list[Path]:
        """Directories containing versioned project test manifests."""
        paths = _table(self.manifest, "tests").get("paths", ["tests"])
        if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
            raise ValidationError(
                "tests.paths must be an array of paths", where=str(self.manifest_path)
            )
        return [self.resolve_path(item) for item in paths]

    def resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            raise ValidationError("project paths must be relative", where=str(self.manifest_path))
        resolved = (self.root / path).resolve()
        if not resolved.is_relative_to(self.root):
            raise ValidationError("project path escapes its root", where=str(self.manifest_path))
        return resolved

    def describe(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "manifest": str(self.manifest_path),
            "environment": self.environment,
            "environment_source": self.environment_source,
            "settings": self.settings,
            "plugin_settings": self.plugin_settings,
            "workflow_paths": [str(path) for path in self.workflow_dirs],
            "test_paths": [str(path) for path in self.test_dirs],
        }


def discover(start: Path | None = None, *, project: Path | None = None) -> Path | None:
    """Find the nearest manifest, or honor an explicit project directory/path."""
    if project is not None:
        candidate = project.resolve()
        manifest = candidate if candidate.name == MANIFEST else candidate / MANIFEST
        if not manifest.is_file():
            raise ValidationError(f"no {MANIFEST} at {manifest}")
        return manifest
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        manifest = candidate / MANIFEST
        if manifest.is_file():
            return manifest
    return None


def load(
    start: Path | None = None, *, project: Path | None = None, env: str | None = None
) -> ProjectContext | None:
    """Load a project context, returning ``None`` for standalone invocations."""
    manifest_path = discover(start, project=project)
    if manifest_path is None:
        return None
    try:
        raw = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise ValidationError(f"invalid TOML: {error}", where=str(manifest_path)) from error
    if not isinstance(raw, dict):
        raise ValidationError("manifest must be a TOML table", where=str(manifest_path))
    _validate(raw, manifest_path)
    environment, source = _environment(raw, manifest_path.parent, env)
    return ProjectContext(manifest_path.parent.resolve(), manifest_path, raw, environment, source)


def _environment(raw: dict[str, Any], root: Path, explicit: str | None) -> tuple[str, str]:
    environments = _table(raw, "environments")
    selected, source = explicit, "--env"
    if selected is None and os.environ.get("SCLPL_ENV"):
        selected, source = os.environ["SCLPL_ENV"], "SCLPL_ENV"
    selection = root / SELECTION
    if selected is None and selection.is_file():
        selected, source = selection.read_text(encoding="utf-8").strip(), "local selection"
    if selected is None:
        selected, source = (
            _table(raw, "project").get("default_environment", "default"),
            "project default",
        )
    if not isinstance(selected, str) or not selected:
        raise ValidationError(
            "environment name must be a non-empty string", where=str(root / MANIFEST)
        )
    if selected not in environments:
        known = ", ".join(sorted(environments)) or "none declared"
        raise ValidationError(
            f"unknown environment {selected!r}; available: {known}", where=str(root / MANIFEST)
        )
    return selected, source


def _validate(raw: dict[str, Any], path: Path) -> None:
    allowed = {
        "project",
        "workflows",
        "tests",
        "environments",
        "auth",
        "policy",
        "outputs",
        "notifications",
        "plugins",
    }
    unknown = set(raw) - allowed
    if unknown:
        raise ValidationError(f"unknown manifest key {sorted(unknown)[0]!r}", where=str(path))
    project = _table(raw, "project")
    schema = project.get("schema", SCHEMA_VERSION)
    if schema != SCHEMA_VERSION:
        raise ValidationError(
            f"unsupported manifest schema {schema!r}; this build supports {SCHEMA_VERSION}",
            where=str(path),
        )
    if "name" in project and not isinstance(project["name"], str):
        raise ValidationError("project.name must be a string", where=str(path))
    environments = _table(raw, "environments")
    if not environments:
        raise ValidationError("manifest must declare at least one environment", where=str(path))
    for name, value in environments.items():
        if not isinstance(name, str) or not isinstance(value, dict):
            raise ValidationError("environments must map names to tables", where=str(path))
        _validate_plugin_tables(_table(value, "plugins"), path)
    for name, value in _table(raw, "plugins").items():
        if not isinstance(name, str) or not isinstance(value, dict):
            raise ValidationError("plugins must map names to tables", where=str(path))
    _validate_plugin_tables(_table(raw, "plugins"), path)


def _table(value: dict[str, Any], name: str) -> dict[str, Any]:
    if not name:
        return value
    found = value.get(name, {})
    if not isinstance(found, dict):
        raise ValidationError(f"{name} must be a table")
    return found


def _merge_tables(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _merge_tables(merged[key], value)
        else:
            merged[key] = value
    return merged


def _validate_plugin_tables(plugins: dict[str, Any], path: Path) -> None:
    """Keep opaque plugin configuration versionable and out of the secret plane."""
    forbidden = {"secret", "password", "token", "account_key", "connection_string", "sas_token"}

    def visit(value: object, trail: str = "") -> None:
        if not isinstance(value, dict):
            return
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValidationError("plugin configuration keys must be strings", where=str(path))
            name = f"{trail}.{key}" if trail else key
            if key.lower() in forbidden:
                raise ValidationError(
                    f"plugin configuration {name!r} may not contain secrets; "
                    "use the environment or host secret store",
                    where=str(path),
                )
            visit(child, name)

    visit(plugins)
