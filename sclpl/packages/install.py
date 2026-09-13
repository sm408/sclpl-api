"""Validate a package archive, then atomically install it. Never runs its code.

Compatibility (a package declaring which `sclpl` versions it needs) and capability
policy (refusing a plugin update that silently claims more than its prior install)
are H3's concern -- they need an installed prior version to compare against. This
module only proves an archive is safe to extract: intact, unmodified since it was
built, and incapable of writing anywhere but its own install directory.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from sclpl.errors import ValidationError
from sclpl.packages.build import PACKAGE_MANIFEST, SCHEMA_VERSION

#: Hard ceilings against a hostile archive. A legitimate project package is source
#: text and small fixtures, not gigabytes of data -- these are refusals, not knobs
#: a package gets to raise from inside the very archive they'd bound.
MAX_ENTRIES = 20_000
MAX_UNCOMPRESSED_TOTAL = 512 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200


@dataclass(frozen=True, slots=True)
class PackageInfo:
    """A validated package's identity, before any of its bytes are extracted."""

    name: str
    version: str
    digest: str
    files: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InstallResult:
    path: Path
    name: str
    version: str
    digest: str


def validate(path: Path) -> PackageInfo:
    """Check a package archive without extracting or executing anything from it.

    Refuses: an unreadable/corrupt zip, an unsupported manifest schema, a missing
    or undeclared entry, a digest mismatch (tampering or corruption), a path that
    escapes the install root (traversal), a symlink or other non-regular entry, a
    collision under case-insensitive comparison, and anything past the archive's
    entry-count, total-size, or per-entry compression-ratio ceiling.
    """
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as error:
        raise ValidationError(f"not a valid package archive: {error}", where=str(path)) from error

    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ENTRIES:
            raise ValidationError(
                f"package has {len(infos)} entries, over the {MAX_ENTRIES} limit", where=str(path)
            )
        manifest = _read_manifest(archive, path)
        _check_entries(infos, manifest, path)
        _check_digests(archive, manifest, path)

    files = tuple(sorted(manifest["files"]))
    return PackageInfo(manifest["name"], manifest["version"], manifest["digest"], files)


def install(path: Path, *, into: Path) -> InstallResult:
    """Validate, then atomically install a package into ``into/<name>/<version>``.

    A failed install never touches an existing good install: every file is
    written into a fresh temporary sibling directory first, and only a final
    atomic rename makes it visible under its real name. Reinstalling the same
    name/version is refused rather than silently overwritten.
    """
    info = validate(path)
    destination = into / info.name / info.version
    if destination.exists():
        raise ValidationError(
            f"{info.name} {info.version} is already installed at {destination}",
            remedies=["remove the existing install first if you mean to reinstall it"],
        )

    into.mkdir(parents=True, exist_ok=True)
    staging = into / f".{info.name}-{info.version}-{uuid4().hex}.tmp"
    staging.mkdir()
    try:
        with zipfile.ZipFile(path) as archive:
            for name in (*info.files, PACKAGE_MANIFEST):
                target = staging / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging.replace(destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    return InstallResult(destination, info.name, info.version, info.digest)


def _read_manifest(archive: zipfile.ZipFile, path: Path) -> dict[str, Any]:
    try:
        raw = archive.read(PACKAGE_MANIFEST)
    except KeyError as error:
        raise ValidationError(f"package is missing {PACKAGE_MANIFEST}", where=str(path)) from error
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValidationError(f"invalid {PACKAGE_MANIFEST}: {error}", where=str(path)) from error
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA_VERSION:
        raise ValidationError("unsupported package manifest schema", where=str(path))
    for key in ("name", "version", "digest", "files"):
        if key not in manifest:
            raise ValidationError(f"package manifest is missing {key!r}", where=str(path))
    if not isinstance(manifest["files"], dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in manifest["files"].items()
    ):
        raise ValidationError("package manifest 'files' must map paths to digests", where=str(path))
    return manifest


def _check_entries(infos: list[zipfile.ZipInfo], manifest: dict[str, Any], path: Path) -> None:
    declared = set(manifest["files"]) | {PACKAGE_MANIFEST}
    present = {info.filename for info in infos}
    missing = declared - present
    if missing:
        raise ValidationError(
            f"package manifest lists missing entry {sorted(missing)[0]!r}", where=str(path)
        )

    seen_casefold: dict[str, str] = {}
    total_uncompressed = 0
    for info in infos:
        name = info.filename
        if name not in declared:
            raise ValidationError(f"undeclared archive entry {name!r}", where=str(path))
        _check_safe_path(name, path)

        # A conforming writer (ours included) often leaves the file-type bits unset
        # entirely -- only a *recognized, dangerous* type (symlink, device, FIFO,
        # socket) is refused; "unset" and "explicitly a regular file" both pass.
        file_type = stat.S_IFMT(info.external_attr >> 16)
        if info.is_dir() or file_type not in (0, stat.S_IFREG):
            raise ValidationError(f"archive entry {name!r} is not a regular file", where=str(path))

        casefolded = name.casefold()
        collision = seen_casefold.get(casefolded)
        if collision is not None and collision != name:
            raise ValidationError(
                f"archive entries {collision!r} and {name!r} collide on a "
                "case-insensitive filesystem",
                where=str(path),
            )
        seen_casefold[casefolded] = name

        total_uncompressed += info.file_size
        if total_uncompressed > MAX_UNCOMPRESSED_TOTAL:
            raise ValidationError(
                f"package exceeds the {MAX_UNCOMPRESSED_TOTAL}-byte uncompressed limit",
                where=str(path),
            )
        ratio = info.file_size / max(info.compress_size, 1)
        if info.compress_size and ratio > MAX_COMPRESSION_RATIO:
            raise ValidationError(
                f"archive entry {name!r} exceeds the compression-ratio limit", where=str(path)
            )


def _check_safe_path(name: str, path: Path) -> None:
    if not name or name.startswith("/") or name.startswith("\\"):
        raise ValidationError(f"unsafe archive entry name {name!r}", where=str(path))
    first_segment = name.split("/", 1)[0]
    if len(first_segment) >= 2 and first_segment[1] == ":":
        raise ValidationError(f"unsafe archive entry name {name!r}", where=str(path))
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValidationError(f"archive entry {name!r} escapes the install root", where=str(path))


def _check_digests(archive: zipfile.ZipFile, manifest: dict[str, Any], path: Path) -> None:
    for name, expected in manifest["files"].items():
        actual = _digest(archive.read(name))
        if actual != expected:
            raise ValidationError(
                f"archive entry {name!r} does not match its manifest digest "
                "(tampered, corrupt, or built by a different sclpl version)",
                where=str(path),
            )
    canonical = json.dumps(manifest["files"], sort_keys=True, separators=(",", ":"))
    if _digest(canonical.encode("utf-8")) != manifest["digest"]:
        raise ValidationError(
            "package manifest digest does not match its file list", where=str(path)
        )


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
