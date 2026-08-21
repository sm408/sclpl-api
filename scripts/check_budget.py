"""Assert the per-package line budget from SPEC section 19.

The budget is the plan's main defence against the thing that produced the tree this
replaced: a package that grows a little on every milestone until nobody can hold it in
their head. Exceeding a budget is not automatically wrong, but it has to be a decision
someone makes on purpose -- so it fails CI, and the number in the SPEC has to move
first.

What counts is *code*: physical lines that are not blank, not wholly a comment, and not
part of a docstring. Prose is excluded deliberately. A budget that counted docstrings
would price explanation against implementation and we would get less of the thing that
is harder to recover later.

Usage:
    python scripts/check_budget.py            # report and gate
    python scripts/check_budget.py --report   # report only, always exit 0
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "sclpl"

# SPEC section 19. Keep this table and the document in step.
BUDGETS: dict[str, int] = {
    "cli": 850,
    "render": 900,
    "catalog": 400,
    "run": 1400,
    "values": 600,
    "expr": 800,
    "tables": 500,
    "ext": 400,
    "state": 400,
    "functions": 900,
}

TOTAL_BUDGET = 7150

_HAS_DOCSTRING = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def _docstring_lines(tree: ast.AST) -> set[int]:
    """Line numbers occupied by docstrings, which the budget does not charge for."""
    lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, _HAS_DOCSTRING):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if not isinstance(first, ast.Expr) or not isinstance(first.value, ast.Constant):
            continue
        if not isinstance(first.value.value, str):
            continue
        end = first.end_lineno if first.end_lineno is not None else first.lineno
        lines.update(range(first.lineno, end + 1))
    return lines


def count_lines(path: Path) -> int:
    source = path.read_text(encoding="utf-8")
    try:
        skip = _docstring_lines(ast.parse(source))
    except SyntaxError:
        skip = set()
    total = 0
    for number, line in enumerate(source.splitlines(), start=1):
        if number in skip:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        total += 1
    return total


def count_package(name: str) -> int:
    directory = PACKAGE / name
    if not directory.is_dir():
        return 0
    return sum(count_lines(path) for path in sorted(directory.rglob("*.py")))


def count_loose() -> int:
    """Modules directly under ``sclpl/`` -- ``__init__`` and ``__main__``."""
    return sum(count_lines(path) for path in sorted(PACKAGE.glob("*.py")))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the sclpl line budget.")
    parser.add_argument("--report", action="store_true", help="Report without failing.")
    args = parser.parse_args()

    if not PACKAGE.is_dir():
        print(f"no package at {PACKAGE}", file=sys.stderr)
        return 1

    over: list[str] = []
    used_total = count_loose()

    print(f"{'package':<12} {'code':>6} {'budget':>7} {'left':>7}")
    print("-" * 35)
    for name, budget in BUDGETS.items():
        used = count_package(name)
        used_total += used
        marker = ""
        if used > budget:
            marker = "  OVER"
            over.append(f"sclpl/{name}: {used} lines against a budget of {budget}")
        print(f"{name:<12} {used:>6} {budget:>7} {budget - used:>7}{marker}")

    print("-" * 35)
    print(f"{'total':<12} {used_total:>6} {TOTAL_BUDGET:>7} {TOTAL_BUDGET - used_total:>7}")

    if used_total > TOTAL_BUDGET:
        over.append(f"total: {used_total} lines against a budget of {TOTAL_BUDGET}")

    if over and not args.report:
        print("\nover budget:", file=sys.stderr)
        for line in over:
            print(f"  {line}", file=sys.stderr)
        print(
            "\nEither delete something, or raise the number in SPEC section 19 on purpose.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
