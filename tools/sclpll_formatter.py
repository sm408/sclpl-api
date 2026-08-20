"""Format a .sclpll file for display.

Usage: python tools/sclpll_formatter.py <file.sclpll>

Reads a .sclpll file and outputs a formatted version to stdout.
"""

from __future__ import annotations

import sys
from pathlib import Path


def format_sclpll(path: Path) -> str:
    """Read and format a .sclpll file. Returns formatted content."""
    content = path.read_text(encoding="utf-8")

    lines = content.splitlines()
    formatted_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            formatted_lines.append("")
            continue
        # Preserve comments
        if stripped.startswith("#"):
            formatted_lines.append(stripped)
            continue
        # Normalize indentation for directives
        if stripped.startswith("@"):
            formatted_lines.append(stripped)
        else:
            # Indent continuation lines
            formatted_lines.append(f"    {stripped}")

    return "\n".join(formatted_lines) + "\n"


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python tools/sclpll_formatter.py <file.sclpll>", file=sys.stderr)
        return 1

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"ERROR: File not found: {path}", file=sys.stderr)
        return 1

    try:
        formatted = format_sclpll(path)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(formatted, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
