"""Constrained file service with path security.

Provides read/write operations scoped to a project root directory with
comprehensive path traversal protection, content-hash conflict detection,
atomic writes, and size limits.

Security constraints enforced:
- Reject absolute paths, drive prefixes, empty segments, ``.`/``..``, NULs
- Reject Windows reserved device names (CON, NUL, PRN, AUX, COM*, LPT*)
- Resolve both parent and target, verify containment within project root
- Reject symlinks or junctions that escape the root
- Write through same-directory temporary file, flush, and atomically replace
- Size limits: 2 MB source, 10 MB request/response preview
- Permit ``.py`` only in functions and approved plugin directories
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import tempfile
from pathlib import Path

from app.web.errors import BadRequestError, ValidationError

logger = logging.getLogger(__name__)

# ── Size limits ──────────────────────────────────────────────────────────

MAX_SOURCE_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_PREVIEW_BYTES = 10 * 1024 * 1024  # 10 MB

# ── Windows reserved device names ────────────────────────────────────────

_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

# ── Allowed extensions ───────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {".py"}
PLUGIN_ALLOWED_EXTENSIONS = {".py", ".json", ".md", ".sclpll", ".txt", ".yaml", ".yml"}


class FileService:
    """Project-root-scoped file operations with security enforcement.

    Parameters
    ----------
    project_root:
        Absolute or relative path to the project root directory.  All
        file operations are confined within this directory.
    allowed_extensions:
        Set of permitted file extensions (including the leading dot).
        If ``None``, all extensions are allowed.
    """

    def __init__(
        self,
        project_root: str | Path,
        allowed_extensions: set[str] | None = None,
    ) -> None:
        self._root = Path(project_root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._allowed = allowed_extensions

    # ── Public API ──────────────────────────────────────────────────────

    @property
    def root(self) -> Path:
        """Resolved project root."""
        return self._root

    def list_tree(self, relative: str = "") -> list[dict]:
        """Return a recursive file tree rooted at *relative*.

        Each entry is ``{"path": str, "name": str, "type": "file"|"dir",
        "size": int}``.  Skips hidden entries (names starting with ``.``).
        """
        base = self._resolve_safe(relative)
        if not base.is_dir():
            raise BadRequestError(message=f"Not a directory: {relative or '/'}")
        return self._walk(base, base)

    def read_file(self, relative: str) -> dict:
        """Read a file and return its content with SHA-256 hash.

        Returns ``{"content": str, "hash": str, "size": int}``.
        """
        path = self._resolve_safe(relative)
        self._check_is_file(path)
        self._check_extension(path)

        size = path.stat().st_size
        if size > MAX_SOURCE_BYTES:
            raise ValidationError(
                message=f"File exceeds {MAX_SOURCE_BYTES} byte limit ({size} bytes).",
                field_errors=[{"field": "path", "message": "File too large."}],
            )

        content = path.read_text(encoding="utf-8")
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return {"content": content, "hash": sha, "size": size}

    def write_file(
        self,
        relative: str,
        content: str,
        *,
        expected_hash: str | None = None,
    ) -> dict:
        """Write content atomically with optional conflict detection.

        If *expected_hash* is provided and does not match the current
        file's SHA-256, a ``409 Conflict`` error is raised.

        Returns ``{"path": str, "hash": str, "size": int}``.
        """
        path = self._resolve_safe(relative)
        self._check_extension(path)

        encoded = content.encode("utf-8")
        if len(encoded) > MAX_SOURCE_BYTES:
            raise ValidationError(
                message=f"Content exceeds {MAX_SOURCE_BYTES} byte limit.",
                field_errors=[{"field": "content", "message": "Content too large."}],
            )

        # Conflict detection
        if expected_hash is not None and path.exists():
            current = path.read_text(encoding="utf-8")
            current_hash = hashlib.sha256(current.encode("utf-8")).hexdigest()
            if current_hash != expected_hash:
                raise ConflictHashError(
                    message="File has been modified since last read.",
                    current_hash=current_hash,
                    expected_hash=expected_hash,
                )

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: temp file in same directory, flush, rename
        self._atomic_write(path, encoded)

        sha = hashlib.sha256(encoded).hexdigest()
        return {"path": relative, "hash": sha, "size": len(encoded)}

    def delete_file(self, relative: str) -> bool:
        """Delete a file within the project root."""
        path = self._resolve_safe(relative)
        if not path.exists():
            return False
        self._check_is_file(path)
        path.unlink()
        return True

    def create_directory(self, relative: str) -> dict:
        """Create a directory within the project root."""
        path = self._resolve_safe(relative)
        path.mkdir(parents=True, exist_ok=True)
        return {"path": relative, "type": "dir"}

    # ── Path validation ─────────────────────────────────────────────────

    def _resolve_safe(self, relative: str) -> Path:
        """Resolve *relative* against the project root with full validation.

        Raises ``BadRequestError`` if the path is absolute, contains
        traversal sequences, uses reserved names, or escapes the root.
        """
        self._validate_segments(relative)

        # Build candidate path and resolve
        candidate = (self._root / relative).resolve()

        # Verify containment
        try:
            candidate.relative_to(self._root)
        except ValueError:
            raise BadRequestError(
                message="Path escapes the project root.",
                field_errors=[{"field": "path", "message": "Path traversal detected."}],
            )

        # Symlink/junction escape check
        if candidate.exists() or candidate.is_symlink():
            real = candidate.resolve()
            try:
                real.relative_to(self._root)
            except ValueError:
                raise BadRequestError(
                    message="Symlink or junction escapes the project root.",
                    field_errors=[{"field": "path", "message": "Symlink escape detected."}],
                )

        return candidate

    def _validate_segments(self, relative: str) -> None:
        """Validate each path segment for forbidden patterns."""
        if not relative:
            return

        # Reject absolute paths
        if os.path.isabs(relative):
            raise BadRequestError(
                message="Absolute paths are not allowed.",
                field_errors=[{"field": "path", "message": "Absolute path rejected."}],
            )

        # Reject drive prefixes on Windows (C:\, D:/, etc.)
        if re.match(r"^[A-Za-z]:", relative):
            raise BadRequestError(
                message="Drive prefixes are not allowed.",
                field_errors=[{"field": "path", "message": "Drive prefix rejected."}],
            )

        # Reject NUL bytes
        if "\x00" in relative:
            raise BadRequestError(
                message="Path contains NUL byte.",
                field_errors=[{"field": "path", "message": "NUL byte rejected."}],
            )

        parts = Path(relative).parts
        for part in parts:
            if not part or part == ".":
                continue

            # Reject .. traversal
            if part == "..":
                raise BadRequestError(
                    message="Path traversal (..) is not allowed.",
                    field_errors=[{"field": "path", "message": "Parent traversal rejected."}],
                )

            # Reject empty segments
            if not part.strip():
                raise BadRequestError(
                    message="Empty path segment.",
                    field_errors=[{"field": "path", "message": "Empty segment rejected."}],
                )

            # Reject Windows reserved names
            stem = Path(part).stem.upper()
            if stem in _WINDOWS_RESERVED:
                raise BadRequestError(
                    message=f"Windows reserved name: {part}",
                    field_errors=[{"field": "path", "message": f"Reserved name '{part}' rejected."}],
                )

    def _check_extension(self, path: Path) -> None:
        """Verify the file extension is in the allowed set."""
        if self._allowed is None:
            return
        if path.suffix.lower() not in self._allowed:
            raise ValidationError(
                message=f"Extension '{path.suffix}' is not allowed.",
                field_errors=[
                    {
                        "field": "path",
                        "message": f"Only {', '.join(sorted(self._allowed))} files are permitted.",
                    }
                ],
            )

    def _check_is_file(self, path: Path) -> None:
        """Verify the path is an existing file."""
        if not path.exists():
            raise NotFoundFileError(path=str(path))
        if not path.is_file():
            raise BadRequestError(
                message=f"Path is not a file: {path.name}",
                field_errors=[{"field": "path", "message": "Expected a file."}],
            )

    # ── Atomic write ────────────────────────────────────────────────────

    def _atomic_write(self, target: Path, data: bytes) -> None:
        """Write *data* to *target* atomically.

        Uses a temporary file in the same directory, flushes, then
        renames.  This ensures readers never see a partial file.
        """
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(target.parent),
            prefix=f".{target.name}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(target))
        except BaseException:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # ── Tree walker ─────────────────────────────────────────────────────

    def _walk(self, directory: Path, root: Path) -> list[dict]:
        """Recursively build a file tree dict list."""
        entries: list[dict] = []
        try:
            items = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return entries

        for item in items:
            if item.name.startswith("."):
                continue

            rel = str(item.relative_to(root)).replace("\\", "/")
            entry: dict = {
                "path": rel,
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
            }
            if item.is_file():
                entry["size"] = item.stat().st_size
            if item.is_dir():
                entry["children"] = self._walk(item, root)
            entries.append(entry)

        return entries


# ── Custom exceptions ────────────────────────────────────────────────────


class ConflictHashError(BadRequestError):
    """SHA-256 hash mismatch on write (stale content)."""

    code = "CONFLICT"
    status_code = 409

    def __init__(
        self,
        message: str = "Content hash mismatch.",
        *,
        current_hash: str = "",
        expected_hash: str = "",
    ) -> None:
        super().__init__(message=message)
        self.current_hash = current_hash
        self.expected_hash = expected_hash


class NotFoundFileError(BadRequestError):
    """File not found on disk."""

    code = "NOT_FOUND"
    status_code = 404

    def __init__(self, message: str = "File not found.", *, path: str = "") -> None:
        super().__init__(message=message)
        self.path = path


# ── Convenience factories ────────────────────────────────────────────────


def create_function_file_service(project_root: str | Path) -> FileService:
    """Create a FileService scoped to a project's ``functions`` directory."""
    func_dir = Path(project_root) / "functions"
    return FileService(func_dir, allowed_extensions=ALLOWED_EXTENSIONS)


def create_plugin_file_service(project_root: str | Path) -> FileService:
    """Create a FileService scoped to a project's ``plugins`` directory."""
    plugin_dir = Path(project_root) / "plugins"
    return FileService(plugin_dir, allowed_extensions=PLUGIN_ALLOWED_EXTENSIONS)
