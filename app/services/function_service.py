"""Function service with AST validation and fixture execution.

Wraps FileService for function CRUD, adds Python AST parsing for
validation (without executing), metadata extraction from docstrings,
and safe fixture execution in a sandboxed context.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import logging
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from app.core.contracts.function_runner import FunctionResult
from app.core.models.context import ExecutionContext
from app.services.file_service import FileService, create_function_file_service
from app.web.errors import BadRequestError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)

# ── Trust acknowledgement store ──────────────────────────────────────────

# Maps (project_id, relative_path, content_hash) -> True when acknowledged
_trust_acknowledgements: dict[tuple[str, str, str], bool] = {}


def _ack_key(project_id: str, path: str, content_hash: str) -> tuple[str, str, str]:
    return (project_id, path, content_hash)


class FunctionService:
    """Service for managing Python transformation functions.

    Parameters
    ----------
    project_id:
        The project identifier for scoping trust acknowledgements.
    project_root:
        Root directory of the project (functions are under ``functions/``).
    """

    def __init__(self, project_id: str, project_root: str | Path) -> None:
        self._project_id = project_id
        self._project_root = Path(project_root)
        self._file_service = create_function_file_service(project_root)

    # ── Discovery ───────────────────────────────────────────────────────

    def list_tree(self) -> list[dict]:
        """Return the function file tree.

        Delegates to the underlying FileService.
        """
        return self._file_service.list_tree("")

    def list_functions(self) -> list[dict]:
        """List all discovered functions with metadata.

        Returns a list of dicts with keys: path, name, description,
        type, category, hash, size.
        """
        tree = self._file_service.list_tree("")
        functions: list[dict] = []
        self._collect_functions(tree, functions)
        return functions

    def get_function(self, relative: str) -> dict:
        """Read a function file with content, hash, and parsed metadata."""
        file_data = self._file_service.read_file(relative)
        content = file_data["content"]
        meta = self._parse_metadata(content)
        ast_result = self.validate_source(content)

        trusted = self.is_trusted(relative, file_data["hash"])

        return {
            "path": relative,
            "name": meta.get("name", Path(relative).stem),
            "description": meta.get("description", ""),
            "type": meta.get("type", "utility"),
            "category": self._infer_category(relative),
            "content": content,
            "hash": file_data["hash"],
            "size": file_data["size"],
            "valid": ast_result["valid"],
            "diagnostics": ast_result["diagnostics"],
            "trusted": trusted,
        }

    def save_function(
        self,
        relative: str,
        content: str,
        *,
        expected_hash: str | None = None,
    ) -> dict:
        """Save function source with AST validation.

        Rejects content that fails AST parsing. Returns the saved
        function metadata with the new hash.
        """
        # Validate AST before writing
        ast_result = self.validate_source(content)
        if not ast_result["valid"]:
            raise ValidationError(
                message="Python source has syntax errors.",
                field_errors=[
                    {"field": "source", "message": d["message"]}
                    for d in ast_result["diagnostics"]
                ],
            )

        # Ensure .py extension
        if not relative.endswith(".py"):
            relative = relative + ".py"

        result = self._file_service.write_file(
            relative, content, expected_hash=expected_hash,
        )

        # Re-read to get full metadata
        meta = self._parse_metadata(content)
        return {
            "path": relative,
            "name": meta.get("name", Path(relative).stem),
            "description": meta.get("description", ""),
            "type": meta.get("type", "utility"),
            "category": self._infer_category(relative),
            "content": content,
            "hash": result["hash"],
            "size": result["size"],
            "valid": True,
            "diagnostics": [],
            "trusted": False,  # new content invalidates trust
        }

    def delete_function(self, relative: str) -> bool:
        """Delete a function file."""
        return self._file_service.delete_file(relative)

    # ── AST validation ──────────────────────────────────────────────────

    def validate_source(self, source: str) -> dict:
        """Parse Python source without executing and return diagnostics.

        Returns ``{"valid": bool, "diagnostics": [...]}``.
        Each diagnostic is ``{"line": int, "column": int,
        "severity": str, "message": str}``.
        """
        diagnostics: list[dict] = []
        try:
            tree = ast.parse(source)
            # Check for a run(ctx) function
            has_run = False
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "run":
                    has_run = True
                    break
            if not has_run:
                diagnostics.append({
                    "line": 1,
                    "column": 0,
                    "severity": "warning",
                    "message": "No 'run(ctx)' function found. The function may not be executable.",
                })
            return {"valid": True, "diagnostics": diagnostics}
        except SyntaxError as exc:
            diagnostics.append({
                "line": exc.lineno or 1,
                "column": exc.offset or 0,
                "severity": "error",
                "message": str(exc.msg) or "Syntax error",
            })
            return {"valid": False, "diagnostics": diagnostics}

    # ── Fixture execution ───────────────────────────────────────────────

    async def run_fixture(
        self,
        relative: str,
        fixture_input: dict | None = None,
        *,
        trusted: bool = False,
    ) -> dict:
        """Execute a function with fixture input.

        Returns ``{"success": bool, "output": Any, "error": str|None,
        "durationMs": int, "stdout": str, "stderr": str}``.

        If *trusted* is not True and the function is not already
        trusted, raises a ``TrustRequiredError``.
        """
        file_data = self._file_service.read_file(relative)
        content = file_data["content"]
        content_hash = file_data["hash"]

        if not trusted and not self.is_trusted(relative, content_hash):
            raise TrustRequiredError(
                message="Trust acknowledgement required before executing this function.",
                path=relative,
                content_hash=content_hash,
            )

        # Build a minimal execution context
        ctx = ExecutionContext()
        ctx.metadata = fixture_input or {}

        # Capture stdout/stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()

        start = time.monotonic()
        try:
            # Write to temp module and execute
            spec = importlib.util.spec_from_file_location("_fixture", str(
                self._project_root / "functions" / relative
            ))
            if spec is None or spec.loader is None:
                return {
                    "success": False,
                    "output": None,
                    "error": f"Could not load module from {relative}",
                    "durationMs": 0,
                    "stdout": "",
                    "stderr": "",
                }

            module = importlib.util.module_from_spec(spec)
            sys.stdout = captured_stdout
            sys.stderr = captured_stderr
            spec.loader.exec_module(module)

            if not hasattr(module, "run"):
                return {
                    "success": False,
                    "output": None,
                    "error": "Function has no 'run(ctx)' entry point",
                    "durationMs": 0,
                    "stdout": captured_stdout.getvalue(),
                    "stderr": captured_stderr.getvalue(),
                }

            import asyncio
            result = module.run(ctx)
            if asyncio.iscoroutine(result):
                result = await result

            elapsed = int((time.monotonic() - start) * 1000)
            return {
                "success": True,
                "output": result,
                "error": None,
                "durationMs": elapsed,
                "stdout": captured_stdout.getvalue(),
                "stderr": captured_stderr.getvalue(),
            }
        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            return {
                "success": False,
                "output": None,
                "error": str(exc),
                "durationMs": elapsed,
                "stdout": captured_stdout.getvalue(),
                "stderr": captured_stderr.getvalue() + "\n" + traceback.format_exc(),
            }
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    # ── Trust management ────────────────────────────────────────────────

    def is_trusted(self, relative: str, content_hash: str) -> bool:
        """Check if the function content is trust-acknowledged."""
        key = _ack_key(self._project_id, relative, content_hash)
        return _trust_acknowledgements.get(key, False)

    def acknowledge_trust(self, relative: str, content_hash: str) -> dict:
        """Acknowledge trust for a specific function content hash."""
        key = _ack_key(self._project_id, relative, content_hash)
        _trust_acknowledgements[key] = True
        return {"path": relative, "hash": content_hash, "trusted": True}

    def revoke_trust(self, relative: str) -> bool:
        """Revoke trust for all content hashes of a function."""
        keys_to_remove = [
            k for k in _trust_acknowledgements
            if k[0] == self._project_id and k[1] == relative
        ]
        for key in keys_to_remove:
            del _trust_acknowledgements[key]
        return len(keys_to_remove) > 0

    # ── Metadata extraction ─────────────────────────────────────────────

    def _parse_metadata(self, source: str) -> dict[str, str]:
        """Extract metadata from a Python file's docstring.

        Looks for ``@key: value`` patterns in the module docstring.
        """
        try:
            tree = ast.parse(source)
            if not tree.body or not isinstance(tree.body[0], ast.Expr):
                return {}
            node = tree.body[0].value
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                return {}
            docstring = node.value
            meta: dict[str, str] = {}
            for line in docstring.strip().splitlines():
                line = line.strip()
                if line.startswith("@"):
                    key, _, value = line[1:].partition(":")
                    meta[key.strip()] = value.strip()
            return meta
        except Exception:
            return {}

    def _infer_category(self, relative: str) -> str:
        """Infer function category from its directory path."""
        parts = Path(relative).parts
        if len(parts) > 1:
            return parts[0]
        return "uncategorized"

    def _collect_functions(self, tree: list[dict], out: list[dict]) -> None:
        """Recursively collect function files from a tree."""
        for entry in tree:
            if entry["type"] == "file" and entry["name"].endswith(".py"):
                try:
                    file_data = self._file_service.read_file(entry["path"])
                    meta = self._parse_metadata(file_data["content"])
                    out.append({
                        "path": entry["path"],
                        "name": meta.get("name", entry["name"][:-3]),
                        "description": meta.get("description", ""),
                        "type": meta.get("type", "utility"),
                        "category": self._infer_category(entry["path"]),
                        "hash": file_data["hash"],
                        "size": file_data["size"],
                    })
                except Exception:
                    # Skip files that can't be read
                    pass
            elif entry["type"] == "dir" and "children" in entry:
                self._collect_functions(entry["children"], out)


# ── Custom exceptions ────────────────────────────────────────────────────


class TrustRequiredError(ValidationError):
    """Trust acknowledgement is required before execution."""

    code = "TRUST_REQUIRED"

    def __init__(
        self,
        message: str = "Trust acknowledgement required.",
        *,
        path: str = "",
        content_hash: str = "",
    ) -> None:
        super().__init__(message=message)
        self.path = path
        self.content_hash = content_hash
