"""Strict, local test manifests; execution is deliberately a separate concern."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sclpl.errors import ValidationError
from sclpl.project.context import ProjectContext

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class Manifest:
    """A test declaration that can later be run in an isolated state directory."""

    path: Path
    workflow: str
    environment: str | None
    inputs: dict[str, Any]
    fixture: Path
    expected_exit: int
    assertions: tuple[dict[str, Any], ...]
    expected_outputs: dict[str, Any]


def discover(project: ProjectContext) -> list[Path]:
    """Find project-local, versioned ``*.test.toml`` files in stable order."""
    return sorted(
        path for root in project.test_dirs if root.is_dir() for path in root.rglob("*.test.toml")
    )


def load(path: Path, project: ProjectContext) -> Manifest:
    """Load one manifest and reject paths that escape the project root."""
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValidationError(f"test manifest not found: {path}") from error
    except tomllib.TOMLDecodeError as error:
        raise ValidationError(f"invalid TOML: {error}", where=str(path)) from error
    if not isinstance(raw, dict):
        raise ValidationError("test manifest must be a TOML table", where=str(path))
    _validate(raw, path)
    fixture = _path(raw["fixture"], path, project)
    return Manifest(
        path=path.resolve(),
        workflow=raw["workflow"],
        environment=raw.get("environment"),
        inputs=raw.get("inputs", {}),
        fixture=fixture,
        expected_exit=raw.get("expected_exit", 0),
        assertions=tuple(raw.get("assertions", [])),
        expected_outputs=raw.get("expected_outputs", {}),
    )


def _validate(raw: dict[str, Any], path: Path) -> None:
    allowed = {
        "schema",
        "workflow",
        "environment",
        "inputs",
        "fixture",
        "expected_exit",
        "assertions",
        "expected_outputs",
    }
    unknown = set(raw) - allowed
    if unknown:
        raise ValidationError(f"unknown test manifest key {sorted(unknown)[0]!r}", where=str(path))
    if raw.get("schema", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise ValidationError("unsupported test manifest schema", where=str(path))
    if not isinstance(raw.get("workflow"), str) or not raw["workflow"]:
        raise ValidationError("workflow must be a non-empty string", where=str(path))
    if not isinstance(raw.get("fixture"), str) or not raw["fixture"]:
        raise ValidationError("fixture must be a relative path", where=str(path))
    if "environment" in raw and not isinstance(raw["environment"], str):
        raise ValidationError("environment must be a string", where=str(path))
    for key in ("inputs", "expected_outputs"):
        if key in raw and not isinstance(raw[key], dict):
            raise ValidationError(f"{key} must be a table", where=str(path))
    if "expected_outputs" in raw and not all(
        isinstance(name, str) and isinstance(value, str) and value
        for name, value in raw["expected_outputs"].items()
    ):
        raise ValidationError("expected_outputs must map steps to JSON files", where=str(path))
    if "expected_exit" in raw and (
        not isinstance(raw["expected_exit"], int) or isinstance(raw["expected_exit"], bool)
    ):
        raise ValidationError("expected_exit must be an integer", where=str(path))
    if "assertions" in raw and (
        not isinstance(raw["assertions"], list)
        or not all(
            isinstance(item, dict)
            and set(item) == {"step", "contract"}
            and all(isinstance(item[key], str) and item[key] for key in item)
            for item in raw["assertions"]
        )
    ):
        raise ValidationError("assertions must contain step and contract strings", where=str(path))


def _path(value: str, manifest: Path, project: ProjectContext) -> Path:
    candidate = (manifest.parent / value).resolve()
    if not candidate.is_relative_to(project.root):
        raise ValidationError("fixture path escapes project root", where=str(manifest))
    return candidate
