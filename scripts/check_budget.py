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

# SPEC section 19, as revised by ADR 0001. A key with a "/" is a sub-package, counted
# on its own and excluded from its parent -- `expr/ops` is a catalogue of operators,
# which grows with the language surface, while `expr` proper is the machinery that
# reads it. Holding them to one number would let either hide growth in the other.
BUDGETS: dict[str, int] = {
    "cli": 2300,
    "render": 1300,
    "catalog": 500,
    "contracts": 700,
    "testing": 700,
    "run": 5000,
    "run/sclpll": 1200,
    "values": 1000,
    "expr": 1500,
    "expr/ops": 1400,
    "tables": 900,
    "ext": 710,
    "state": 920,
    "functions": 1200,
    "plugins_bundled": 600,
    "project": 1200,
    "packages": 1600,
}

TOTAL_BUDGET = 23320

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
    """Lines in ``name``, excluding any sub-package that has its own budget."""
    directory = PACKAGE / name
    if not directory.is_dir():
        return 0
    nested = [PACKAGE / key for key in BUDGETS if key != name and key.startswith(f"{name}/")]
    total = 0
    for path in sorted(directory.rglob("*.py")):
        if any(path.is_relative_to(child) for child in nested):
            continue
        total += count_lines(path)
    return total


def count_loose() -> int:
    """Modules directly under ``sclpl/`` -- ``__init__`` and ``__main__``."""
    return sum(count_lines(path) for path in sorted(PACKAGE.glob("*.py")))


def unbudgeted_packages() -> list[str]:
    """Top-level Python packages that would otherwise evade the line budget."""
    budgeted = {name.split("/", 1)[0] for name in BUDGETS}
    return sorted(
        path.name
        for path in PACKAGE.iterdir()
        if path.is_dir() and (path / "__init__.py").is_file() and path.name not in budgeted
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the sclpl line budget.")
    parser.add_argument("--report", action="store_true", help="Report without failing.")
    args = parser.parse_args()

    if not PACKAGE.is_dir():
        print(f"no package at {PACKAGE}", file=sys.stderr)
        return 1

    over: list[str] = []
    over.extend(f"unbudgeted package: sclpl/{name}" for name in unbudgeted_packages())
    used_total = count_loose()

    width = max(12, max(len(name) for name in BUDGETS) + 1)
    print(f"{'package':<{width}} {'code':>6} {'budget':>7} {'left':>7}")
    print("-" * (width + 23))
    for name, budget in BUDGETS.items():
        used = count_package(name)
        used_total += used
        marker = ""
        if used > budget:
            marker = "  OVER"
            over.append(f"sclpl/{name}: {used} lines against a budget of {budget}")
        print(f"{name:<{width}} {used:>6} {budget:>7} {budget - used:>7}{marker}")

    print("-" * (width + 23))
    print(f"{'total':<{width}} {used_total:>6} {TOTAL_BUDGET:>7} {TOTAL_BUDGET - used_total:>7}")

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
