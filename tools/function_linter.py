"""Lint Python function files in a directory.

Usage: python tools/function_linter.py <functions_dir>

Checks:
- Each .py file (except __init__.py) has a docstring
- Each .py file has a 'run' function or class with 'run' method
- No syntax errors
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def lint_function_file(path: Path) -> list[str]:
    """Lint a single Python function file. Returns list of errors."""
    errors: list[str] = []

    try:
        source = path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"Cannot read {path.name}: {e}"]

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        return [f"Syntax error in {path.name}: {e}"]

    # Check for docstring
    docstring = ast.get_docstring(tree)
    if not docstring:
        errors.append(f"{path.name}: missing module docstring")

    # Check for run function or class with run method
    has_run = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run":
            has_run = True
            break
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "run":
                    has_run = True
                    break

    if not has_run:
        errors.append(f"{path.name}: no 'run' function found")

    return errors


def lint_functions_dir(directory: Path) -> list[str]:
    """Lint all Python function files in a directory."""
    errors: list[str] = []

    if not directory.exists():
        return [f"Directory not found: {directory}"]

    py_files = sorted(directory.glob("*.py"))
    if not py_files:
        return [f"No Python files found in {directory}"]

    for py_file in py_files:
        if py_file.name.startswith("_"):
            continue
        file_errors = lint_function_file(py_file)
        errors.extend(file_errors)

    return errors


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python tools/function_linter.py <functions_dir>", file=sys.stderr)
        return 1

    directory = Path(sys.argv[1])
    errors = lint_functions_dir(directory)

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    print(f"OK: All functions in {directory.name} pass linting")
    return 0


if __name__ == "__main__":
    sys.exit(main())
