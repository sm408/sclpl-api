from __future__ import annotations

import ast
import asyncio
import importlib.util
import logging
import time
from pathlib import Path

from app.core.contracts.function_runner import FunctionResult, FunctionRunner
from app.core.models.context import ExecutionContext

logger = logging.getLogger(__name__)


class FilesystemFunctionRunner(FunctionRunner):
    def __init__(self, base_dir: str | Path = "functions") -> None:
        self._base = Path(base_dir)

    def discover(self, directory: str | None = None) -> list[dict[str, str]]:
        search_dir = Path(directory) if directory else self._base
        if not search_dir.exists():
            return []

        functions: list[dict[str, str]] = []
        for py_file in search_dir.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue
            meta = self._parse_metadata(py_file)
            if meta:
                functions.append(meta)
        return functions

    async def run(
        self,
        name: str,
        ctx: ExecutionContext,
    ) -> FunctionResult:
        func_path = self._find_function(name)
        if not func_path:
            return FunctionResult(name=name, success=False, error=f"Function '{name}' not found")

        start = time.monotonic()
        try:
            spec = importlib.util.spec_from_file_location(name, func_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if not hasattr(module, "run"):
                return FunctionResult(
                    name=name, success=False, error=f"Function '{name}' has no run(ctx) entrypoint"
                )

            result = module.run(ctx)
            if asyncio.iscoroutine(result):
                result = await result

            elapsed = int((time.monotonic() - start) * 1000)
            return FunctionResult(
                name=name, success=True, return_value=result, duration_ms=elapsed
            )
        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            logger.exception("Function %s failed", name)
            return FunctionResult(
                name=name, success=False, error=str(exc), duration_ms=elapsed
            )

    def _find_function(self, name: str) -> Path | None:
        for py_file in self._base.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue
            meta = self._parse_metadata(py_file)
            if meta and meta.get("name") == name:
                return py_file
            if py_file.stem == name:
                return py_file
        return None

    def _parse_metadata(self, path: Path) -> dict[str, str] | None:
        try:
            content = path.read_text(encoding="utf-8")
            tree = ast.parse(content)

            if not tree.body or not isinstance(tree.body[0], ast.Expr):
                return None

            node = tree.body[0].value
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                return None

            docstring = node.value
            meta: dict[str, str] = {"path": str(path)}
            for line in docstring.strip().splitlines():
                line = line.strip()
                if line.startswith("@"):
                    key, _, value = line[1:].partition(":")
                    meta[key.strip()] = value.strip()

            if "name" in meta:
                return meta
            return None
        except Exception:
            return None
