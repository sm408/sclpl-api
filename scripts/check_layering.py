"""Measure the import graph between packages, and refuse a cycle.

A claim like "decoupled" is worth exactly as much as the thing that checks it. This
reads every import in `sclpl/` and reports which package depends on which, so the
architecture notes cite a measurement rather than an intention.

**What counts as a cycle.** Two packages importing each other at module scope. Two
exceptions, both deliberate:

- the package root, `sclpl/`, holds `__init__` and `bootstrap`. It is the entry point,
  so it names the CLI and the CLI names it back. That is what an entry point is.
- an import inside a function body is a deferral, not a dependency. `bootstrap` reaches
  for the plugin loader that way precisely so the engine works without one.

Run it with `--graph` for a Mermaid diagram, which is what the vault embeds.
"""

from __future__ import annotations

import argparse
import ast
import sys
from collections import defaultdict
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "sclpl"

#: Packages budgeted and reasoned about separately from their parent.
SPLIT = {("expr", "ops"), ("run", "sclpll")}

#: The package root. Cycles through it are the entry point, not coupling.
ROOT = "sclpl"


def package_of(path: Path) -> str:
    parts = path.relative_to(PACKAGE).parts[:-1]
    if not parts:
        return ROOT
    if len(parts) >= 2 and (parts[0], parts[1]) in SPLIT:
        return f"{parts[0]}/{parts[1]}"
    return parts[0]


def package_of_module(dotted: str) -> str | None:
    if not dotted.startswith(f"{ROOT}."):
        return ROOT if dotted == ROOT else None
    parts = dotted.split(".")[1:]
    if len(parts) == 1:
        return ROOT
    if len(parts) >= 2 and (parts[0], parts[1]) in SPLIT:
        return f"{parts[0]}/{parts[1]}"
    return parts[0]


def deferred_imports(tree: ast.AST) -> set[int]:
    """Imports inside a function body: a deferral, not a dependency."""
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(node):
                if isinstance(inner, (ast.Import, ast.ImportFrom)):
                    found.add(id(inner))
    return found


def scan() -> tuple[dict[tuple[str, str], set[str]], set[str]]:
    edges: dict[tuple[str, str], set[str]] = defaultdict(set)
    packages: set[str] = set()

    for path in sorted(PACKAGE.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        here = package_of(path)
        packages.add(here)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        lazy = deferred_imports(tree)

        for node in ast.walk(tree):
            if id(node) in lazy:
                continue
            named: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                named = [node.module]
            elif isinstance(node, ast.Import):
                named = [alias.name for alias in node.names]
            for dotted in named:
                there = package_of_module(dotted)
                if there and there != here:
                    edges[(here, there)].add(path.name)
    return edges, packages


def cycles(edges: dict[tuple[str, str], set[str]]) -> list[tuple[str, str]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for source, target in edges:
        adjacency[source].add(target)

    found: list[tuple[str, str]] = []
    for source in sorted(adjacency):
        for target in sorted(adjacency[source]):
            if source == ROOT or target == ROOT:
                continue  # the entry point, not coupling
            if source in adjacency.get(target, set()):
                pair = (min(source, target), max(source, target))
                if pair not in found:
                    found.append(pair)
    return found


def mermaid(edges: dict[tuple[str, str], set[str]], packages: set[str]) -> str:
    lines = ["flowchart TD"]
    for name in sorted(packages):
        if name == ROOT:
            continue
        lines.append(f'    {name.replace("/", "_")}["{name}/"]')
    for (source, target), files in sorted(edges.items()):
        if ROOT in (source, target):
            continue
        arrow = "-->" if len(files) > 1 else "-.->"
        lines.append(f"    {source.replace('/', '_')} {arrow} {target.replace('/', '_')}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check sclpl's package layering.")
    parser.add_argument("--graph", action="store_true", help="Print a Mermaid diagram.")
    parser.add_argument("--report", action="store_true", help="Report without failing.")
    args = parser.parse_args()

    edges, packages = scan()

    if args.graph:
        print(mermaid(edges, packages))
        return 0

    fan_out: dict[str, int] = defaultdict(int)
    fan_in: dict[str, int] = defaultdict(int)
    for source, target in edges:
        fan_out[source] += 1
        fan_in[target] += 1

    width = max(len(name) for name in packages) + 1
    print(f"{'package':<{width}} {'out':>4} {'in':>4}")
    print("-" * (width + 10))
    for name in sorted(packages):
        print(f"{name:<{width}} {fan_out[name]:>4} {fan_in[name]:>4}")

    found = cycles(edges)
    print(f"\n{len(edges)} edges between {len(packages)} packages")
    if not found:
        print("no cycles")
        return 0

    print("\ncycles:", file=sys.stderr)
    for source, target in found:
        print(f"  {source} <-> {target}", file=sys.stderr)
        for pair in ((source, target), (target, source)):
            print(f"    {pair[0]} -> {pair[1]}: {', '.join(sorted(edges[pair]))}", file=sys.stderr)
    print(
        "\nOne of the two directions is the wrong way round. Move what is shared to the "
        "package that owns the concept, or defer the import if it is genuinely optional.",
        file=sys.stderr,
    )
    return 0 if args.report else 1


if __name__ == "__main__":
    raise SystemExit(main())
