"""
Function Linter for SCLPLAPI

Checks function files for:
- Proper metadata docstring (@name, @type, @version)
- run(ctx) entrypoint exists
- Proper return statement
- Style issues (bare except, missing imports, etc.)

Usage:
    python tools/function_linter.py <file_or_directory> [--functions-dir functions]
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


class LintResult:
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []

    @property
    def clean(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, msg: str) -> None:
        self.errors.append(f"ERROR: {self.filepath}: {msg}")

    def add_warning(self, msg: str) -> None:
        self.warnings.append(f"WARN:  {self.filepath}: {msg}")

    def add_info(self, msg: str) -> None:
        self.info.append(f"INFO:  {self.filepath}: {msg}")


def lint_function(filepath: Path) -> LintResult:
    result = LintResult(str(filepath))

    try:
        source = filepath.read_text(encoding="utf-8")
    except OSError as e:
        result.add_error(f"Cannot read file: {e}")
        return result

    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as e:
        result.add_error(f"Syntax error at line {e.lineno}: {e.msg}")
        return result

    _check_metadata(tree, result)
    _check_run_entrypoint(tree, result)
    _check_return_statement(tree, result)
    _check_style_issues(tree, source, result)
    _check_imports(tree, result)

    return result


def _check_metadata(tree: ast.Module, result: LintResult) -> None:
    if not tree.body or not isinstance(tree.body[0], ast.Expr):
        result.add_error("Missing metadata docstring at top of file")
        return

    node = tree.body[0].value
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        result.add_error("First statement must be a docstring with metadata")
        return

    docstring = node.value
    meta: dict[str, str] = {}
    for line in docstring.strip().splitlines():
        line = line.strip()
        if line.startswith("@"):
            key, _, value = line[1:].partition(":")
            meta[key.strip()] = value.strip()

    if "name" not in meta:
        result.add_error("Metadata missing @name")
    if "type" not in meta:
        result.add_error("Metadata missing @type")
    else:
        valid_types = {
            "pre_request", "post_response", "auth_token",
            "transformer", "analytics", "validator", "exporter", "workflow_node",
        }
        if meta["type"] not in valid_types:
            result.add_warning(f"Unknown @type '{meta['type']}' (expected: {', '.join(sorted(valid_types))})")
    if "version" not in meta:
        result.add_warning("Metadata missing @version (recommended)")

    result.add_info(f"@name={meta.get('name', '?')} @type={meta.get('type', '?')}")


def _check_run_entrypoint(tree: ast.Module, result: LintResult) -> None:
    run_funcs = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "run"
    ]

    if not run_funcs:
        result.add_error("Missing run(ctx) entrypoint function")
        return

    run_func = run_funcs[0]
    args = run_func.args
    all_args = args.args + args.posonlyargs + args.kwonlyargs
    arg_names = [a.arg for a in all_args]

    if not arg_names or arg_names[0] != "ctx":
        result.add_error("run() must accept 'ctx' as first parameter")
    if len(all_args) < 1:
        result.add_error("run() must accept at least one parameter (ctx)")


def _check_return_statement(tree: ast.Module, result: LintResult) -> None:
    run_funcs = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "run"
    ]

    if not run_funcs:
        return

    run_func = run_funcs[0]
    has_return = False
    for node in ast.walk(run_func):
        if isinstance(node, ast.Return):
            has_return = True
            break

    if not has_return:
        result.add_warning("run() has no return statement (should return ctx)")


def _check_style_issues(tree: ast.Module, source: str, result: LintResult) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            result.add_warning(f"Line {node.lineno}: Bare 'except:' clause (use 'except Exception:')")

    lines = source.splitlines()
    for i, line in enumerate(lines, 1):
        if len(line) > 120:
            result.add_info(f"Line {i}: Line length {len(line)} exceeds 120 chars")


def _check_imports(tree: ast.Module, result: LintResult) -> None:
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_names.add(node.module.split(".")[0])

    used_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            used_names.add(node.value.id)

    unused = imported_names - used_names - {"__future__"}
    if unused:
        result.add_info(f"Potentially unused imports: {', '.join(sorted(unused))}")


def lint_directory(directory: Path) -> list[LintResult]:
    results: list[LintResult] = []
    for py_file in sorted(directory.rglob("*.py")):
        if py_file.name.startswith("_"):
            continue
        results.append(lint_function(py_file))
    return results


def print_report(results: list[LintResult]) -> bool:
    all_clean = True
    total_errors = 0
    total_warnings = 0

    for result in results:
        if not result.clean:
            all_clean = False
        total_errors += len(result.errors)
        total_warnings += len(result.warnings)

        for msg in result.errors:
            print(msg)
        for msg in result.warnings:
            print(msg)
        for msg in result.info:
            print(msg)

    print()
    if all_clean and total_warnings == 0:
        print(f"OK: {len(results)} files, 0 errors, 0 warnings")
    else:
        print(f"SUMMARY: {len(results)} files, {total_errors} errors, {total_warnings} warnings")

    return all_clean


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    target = Path(sys.argv[1])
    if "--functions-dir" in sys.argv:
        idx = sys.argv.index("--functions-dir")
        if idx + 1 < len(sys.argv):
            target = Path(sys.argv[idx + 1])

    if target.is_file():
        results = [lint_function(target)]
    elif target.is_dir():
        results = lint_directory(target)
    else:
        print(f"ERROR: Not found: {target}", file=sys.stderr)
        sys.exit(1)

    all_clean = print_report(results)
    sys.exit(0 if all_clean else 1)


if __name__ == "__main__":
    main()
