"""Bundle a project's declared surface into one reproducible `.sclplpkg` archive."""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sclpl.errors import ValidationError
from sclpl.project import policy
from sclpl.project.context import ProjectContext

#: The manifest entry every archive carries, listing every other entry's digest.
PACKAGE_MANIFEST = "PACKAGE.json"
SCHEMA_VERSION = 1

#: The oldest timestamp the ZIP format accepts. Fixed so two builds of identical
#: content produce identical bytes, on any machine, on any day.
_FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)
_FILE_MODE = 0o644 << 16
_SECRET_SUFFIXES = (".pem", ".key")


@dataclass(frozen=True, slots=True)
class BuildResult:
    """What `sclpl package build` produced."""

    path: Path
    name: str
    version: str
    digest: str
    files: tuple[str, ...]


def build(context: ProjectContext, *, out: Path | None = None) -> BuildResult:
    """Bundle a project's declared surface into one reproducible archive.

    Building never executes project code: it only reads and hashes files the
    project context already knows how to enumerate (workflow/test directories,
    conventional `docs`/`schemas`/`fixtures`/`plugins` directories, declared
    `[package.include]` globs, and locally-registered Python scripts). Secrets,
    declared output roots, `.sclpl/` local state, and hidden files never qualify.
    """
    name, version = _identity(context)
    collected = _collect(context)
    digest, entries = _digest_files(collected)
    manifest = {
        "schema": SCHEMA_VERSION,
        "name": name,
        "version": version,
        "digest": digest,
        "files": entries,
    }

    destination = out or (context.root / "dist" / f"{name}-{version}.sclplpkg")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    _write_archive(temporary, collected, manifest)
    temporary.replace(destination)

    return BuildResult(destination, name, version, digest, tuple(sorted(collected)))


def _identity(context: ProjectContext) -> tuple[str, str]:
    package = context.package
    name, version = package.get("name"), package.get("version")
    if not isinstance(name, str) or not name:
        raise ValidationError(
            "package.name is required to build a package",
            where=str(context.manifest_path),
            remedies=["add a [package] table with name and version"],
        )
    if not isinstance(version, str) or not version:
        raise ValidationError(
            "package.version is required to build a package",
            where=str(context.manifest_path),
            remedies=['add version to the [package] table, e.g. version = "0.1.0"'],
        )
    return name, version


def _collect(context: ProjectContext) -> dict[str, Path]:
    """Map archive-relative POSIX paths to source files, in deterministic order."""
    root = context.root
    excluded_roots = policy.parse(context).output_roots
    collected: dict[str, Path] = {}

    def add_tree(base: Path) -> None:
        if not base.is_dir():
            return
        for path in sorted(base.rglob("*")):
            if path.is_file() and not _is_excluded(path, root, excluded_roots):
                collected[path.relative_to(root).as_posix()] = path

    collected[context.manifest_path.relative_to(root).as_posix()] = context.manifest_path
    lock_path = root / "sclpl.lock"
    if lock_path.is_file():
        collected["sclpl.lock"] = lock_path

    for directory in (*context.workflow_dirs, *context.test_dirs):
        add_tree(directory)
    for conventional in ("docs", "schemas", "fixtures", "plugins"):
        add_tree(root / conventional)
    for pattern in context.package.get("include", []):
        for path in sorted(root.glob(pattern)):
            if path.is_file() and not _is_excluded(path, root, excluded_roots):
                collected[path.relative_to(root).as_posix()] = path

    scripts = context.manifest.get("python", {})
    scripts = scripts.get("scripts", {}) if isinstance(scripts, dict) else {}
    for script in scripts.values() if isinstance(scripts, dict) else ():
        local = script.get("path") if isinstance(script, dict) else None
        if isinstance(local, str):
            candidate = context.resolve_path(local)
            if candidate.is_file() and not _is_excluded(candidate, root, excluded_roots):
                collected[candidate.relative_to(root).as_posix()] = candidate

    return collected


def _is_excluded(path: Path, root: Path, excluded_roots: tuple[Path, ...]) -> bool:
    """Refuse hidden paths, caches, declared outputs, and anything secret-shaped."""
    relative = path.relative_to(root)
    if any(part.startswith(".") for part in relative.parts):
        return True
    if "__pycache__" in relative.parts or path.suffix == ".pyc":
        return True
    if path.suffix in _SECRET_SUFFIXES or path.name.startswith(".env"):
        return True
    return any(path.is_relative_to(excluded) for excluded in excluded_roots)


def _digest_files(collected: dict[str, Path]) -> tuple[str, dict[str, str]]:
    entries = {name: _digest(collected[name].read_bytes()) for name in sorted(collected)}
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":"))
    return _digest(canonical.encode("utf-8")), entries


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_archive(destination: Path, collected: dict[str, Path], manifest: dict[str, Any]) -> None:
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        rendered = json.dumps(manifest, sort_keys=True, indent=2).encode("utf-8") + b"\n"
        _write_entry(archive, PACKAGE_MANIFEST, rendered)
        for name in sorted(collected):
            _write_entry(archive, name, collected[name].read_bytes())


def _write_entry(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=_FIXED_DATE_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = _FILE_MODE
    # Unix, always: otherwise the same content zipped on Windows and on Linux CI
    # would carry a different `create_system` byte and fail the determinism promise.
    info.create_system = 3
    archive.writestr(info, data)
