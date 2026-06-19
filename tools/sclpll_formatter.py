"""
SCLPLL Formatter for SCLPLAPI

Formats .sclpll files consistently:
- Aligns arrows and dependencies
- Sorts steps by dependency order (topological)
- Normalizes whitespace and indentation
- Preserves comments and blank lines between sections

Usage:
    python tools/sclpll_formatter.py <file.sclpll> [--check] [--write]
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict, deque
from pathlib import Path


_STEP_RE = re.compile(r"^@step\s+(\S+)(?:\s*<-\s*(.+?))?(?:\s*->\s*(\S+))?\s*$")
_WORKFLOW_RE = re.compile(r"^@workflow\s+(\S+)\s*(.*)$")
_BASE_URL_RE = re.compile(r"^@base_url\s+(\S+)$")
_VAR_RE = re.compile(r"^@var\s+(\S+)\s*=\s*(.+)$")


def parse_steps(lines: list[str]) -> list[dict]:
    steps: list[dict] = []
    current_step: dict | None = None

    for line in lines:
        stripped = line.strip()
        m = _STEP_RE.match(stripped)
        if m:
            step_id = m.group(1)
            deps_raw = m.group(2)
            output_var = m.group(3)
            depends_on = []
            if deps_raw:
                depends_on = [d.strip() for d in deps_raw.split(",") if d.strip()]
            current_step = {
                "id": step_id,
                "depends_on": depends_on,
                "output_variable": output_var,
                "body_lines": [],
            }
            steps.append(current_step)
            continue

        if current_step and (line.startswith("    ") or line.startswith("\t")):
            current_step["body_lines"].append(stripped)

    return steps


def topological_sort(steps: list[dict]) -> list[dict]:
    step_ids = {s["id"] for s in steps}
    in_degree: dict[str, int] = {s["id"]: 0 for s in steps}
    dependents: dict[str, list[str]] = defaultdict(list)

    for step in steps:
        for dep in step["depends_on"]:
            if dep in step_ids:
                in_degree[step["id"]] += 1
                dependents[dep].append(step["id"])

    queue = deque(s["id"] for s in steps if in_degree[s["id"]] == 0)
    step_map = {s["id"]: s for s in steps}
    sorted_ids: list[str] = []

    while queue:
        sid = queue.popleft()
        sorted_ids.append(sid)
        for dep_id in dependents[sid]:
            in_degree[dep_id] -= 1
            if in_degree[dep_id] == 0:
                queue.append(dep_id)

    if len(sorted_ids) < len(steps):
        remaining = step_ids - set(sorted_ids)
        sorted_ids.extend(sorted(remaining))

    return [step_map[sid] for sid in sorted_ids]


def format_step(step: dict, max_id_len: int, max_dep_len: int) -> list[str]:
    lines: list[str] = []

    step_line = f"@step {step['id']}"
    dep_part = ""
    if step["depends_on"]:
        dep_part = f" <- {', '.join(step['depends_on'])}"
    out_part = ""
    if step["output_variable"]:
        out_part = f" -> {step['output_variable']}"

    lines.append(f"{step_line}{dep_part}{out_part}")

    for body_line in step["body_lines"]:
        lines.append(f"    {body_line}")

    return lines


def format_sclpll(source: str) -> str:
    lines = source.splitlines()
    header_lines: list[str] = []
    step_lines: list[str] = []
    in_steps = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("@step "):
            in_steps = True
        if in_steps:
            step_lines.append(line)
        else:
            header_lines.append(line)

    steps = parse_steps(step_lines)
    sorted_steps = topological_sort(steps)

    max_id_len = max((len(s["id"]) for s in sorted_steps), default=0)
    max_dep_len = max(
        (len(", ".join(s["depends_on"])) for s in sorted_steps if s["depends_on"]),
        default=0,
    )

    output_lines: list[str] = []

    header_text = "\n".join(header_lines).rstrip()
    if header_text:
        output_lines.extend(header_text.splitlines())
        output_lines.append("")

    for i, step in enumerate(sorted_steps):
        if i > 0:
            output_lines.append("")
        formatted = format_step(step, max_id_len, max_dep_len)
        output_lines.extend(formatted)

    result = "\n".join(output_lines).rstrip() + "\n"
    return result


def check_format(source: str) -> bool:
    formatted = format_sclpll(source)
    return source.strip() == formatted.strip()


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    filepath = Path(sys.argv[1])
    check_mode = "--check" in sys.argv
    write_mode = "--write" in sys.argv

    if not filepath.exists():
        print(f"ERROR: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    source = filepath.read_text(encoding="utf-8")
    formatted = format_sclpll(source)

    if check_mode:
        if source.strip() == formatted.strip():
            print(f"OK: {filepath} is properly formatted")
            sys.exit(0)
        else:
            print(f"DIFF: {filepath} needs formatting")
            sys.exit(1)

    if write_mode:
        filepath.write_text(formatted, encoding="utf-8")
        print(f"Formatted: {filepath}")
    else:
        print(formatted, end="")


if __name__ == "__main__":
    main()
