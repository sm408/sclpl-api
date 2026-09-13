"""H3: inspect, verify, diff, and remove installed packages -- the locked inventory
`sclpl package install` (H2) built. Nothing here re-validates archive safety; that
already happened once, at install time.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from sclpl.errors import ValidationError
from sclpl.packages.build import PACKAGE_MANIFEST


@dataclass(frozen=True, slots=True)
class InstalledPackage:
    name: str
    version: str
    path: Path
    digest: str


@dataclass(frozen=True, slots=True)
class Diff:
    """What changed between two installed manifests' file listings."""

    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.changed)


def list_installed(root: Path) -> list[InstalledPackage]:
    """Every installed `<name>/<version>` under an install root, oldest API first."""
    if not root.is_dir():
        return []
    found: list[InstalledPackage] = []
    for name_dir in sorted(root.iterdir()):
        if not name_dir.is_dir():
            continue
        for version_dir in sorted(name_dir.iterdir()):
            manifest_path = version_dir / PACKAGE_MANIFEST
            if not manifest_path.is_file():
                continue
            manifest = _read_manifest(manifest_path)
            digest = manifest["digest"]
            assert isinstance(digest, str)
            found.append(InstalledPackage(name_dir.name, version_dir.name, version_dir, digest))
    return found


def describe(root: Path, name: str, version: str) -> dict[str, object]:
    """The installed manifest for one `name`/`version`, as recorded at install time."""
    manifest_path = _installed_path(root, name, version) / PACKAGE_MANIFEST
    if not manifest_path.is_file():
        raise ValidationError(
            f"{name} {version} is not installed under {root}",
            remedies=["run sclpl package list to see what is installed"],
        )
    return _read_manifest(manifest_path)


def verify(root: Path, name: str, version: str) -> None:
    """Re-hash every installed file against its own recorded manifest.

    Unlike H2's install-time `validate`, this checks the files actually sitting on
    disk today -- catching drift from anything that touched the install directory
    after installation, not just a corrupt or tampered archive before it.
    """
    destination = _installed_path(root, name, version)
    manifest = describe(root, name, version)
    files = manifest["files"]
    assert isinstance(files, dict)
    for relative, expected in files.items():
        target = destination / relative
        if not target.is_file():
            raise ValidationError(f"{name} {version} is missing {relative}", where=str(destination))
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != expected:
            raise ValidationError(
                f"{name} {version} file {relative!r} no longer matches its installed digest",
                where=str(destination),
                remedies=["reinstall the package from a trusted archive"],
            )


def diff(root: Path, name: str, old_version: str, new_version: str) -> Diff:
    """Compare two installed versions' file listings and per-file digests."""
    old_files = _files_of(root, name, old_version)
    new_files = _files_of(root, name, new_version)
    added = tuple(sorted(set(new_files) - set(old_files)))
    removed = tuple(sorted(set(old_files) - set(new_files)))
    changed = tuple(
        sorted(
            name_
            for name_ in set(old_files) & set(new_files)
            if old_files[name_] != new_files[name_]
        )
    )
    return Diff(added, removed, changed)


def remove(
    root: Path,
    name: str,
    version: str,
    *,
    required_by: dict[str, str] | None = None,
    force: bool = False,
) -> None:
    """Remove one installed `name`/`version`, refusing while a project pins it.

    `required_by` is a project's `[package.requires]` table (name -> pinned
    version). A pin on exactly this version is a real, checkable reason not to
    remove it silently -- `--force` is the explicit override.
    """
    destination = _installed_path(root, name, version)
    if not destination.is_dir():
        raise ValidationError(f"{name} {version} is not installed under {root}")
    pinned = (required_by or {}).get(name)
    if pinned == version and not force:
        raise ValidationError(
            f"{name} {version} is required by the current project's [package.requires]",
            remedies=[
                "update or drop the pin in [package.requires] first",
                "pass --force to remove it anyway",
            ],
        )
    shutil.rmtree(destination)
    parent = destination.parent
    if parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()


def _installed_path(root: Path, name: str, version: str) -> Path:
    return root / name / version


def _files_of(root: Path, name: str, version: str) -> dict[str, str]:
    manifest = describe(root, name, version)
    files = manifest["files"]
    assert isinstance(files, dict)
    return files


def _read_manifest(path: Path) -> dict[str, object]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValidationError(f"invalid {PACKAGE_MANIFEST}: {error}", where=str(path)) from error
    if not isinstance(parsed, dict):
        raise ValidationError(f"{PACKAGE_MANIFEST} must be a JSON object", where=str(path))
    return parsed
