"""Validate a workflow.json file.

Usage: python tools/workflow_validator.py <workflow.json>

Checks:
- File is valid JSON
- Has required fields: id, name, steps
- Steps have id and type
- No duplicate step IDs
- Dependencies reference valid steps
- No circular dependencies
"""

from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path


def validate_workflow(path: Path) -> list[str]:
    """Validate a workflow.json file. Returns list of errors (empty = valid)."""
    errors: list[str] = []

    if not path.exists():
        return [f"File not found: {path}"]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]

    if not isinstance(data, dict):
        return ["Workflow must be a JSON object"]

    for field in ("id", "name", "steps"):
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if "steps" not in data:
        return errors

    steps = data["steps"]
    if not isinstance(steps, list) or len(steps) == 0:
        errors.append("Steps must be a non-empty array")
        return errors

    step_ids: set[str] = set()
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            errors.append(f"Step {i} must be a JSON object")
            continue
        if "id" not in step:
            errors.append(f"Step {i} missing 'id'")
        elif step["id"] in step_ids:
            errors.append(f"Duplicate step ID: {step['id']}")
        else:
            step_ids.add(step["id"])
        if "type" not in step:
            errors.append(f"Step {i} missing 'type'")

    # Check dependencies reference valid steps
    for step in steps:
        if not isinstance(step, dict):
            continue
        for dep in step.get("depends_on", []):
            if dep not in step_ids:
                errors.append(f"Step '{step.get('id', '?')}' depends on unknown step '{dep}'")

    # Check for cycles (topological sort)
    if step_ids:
        in_degree: dict[str, int] = {sid: 0 for sid in step_ids}
        dependents: dict[str, list[str]] = {sid: [] for sid in step_ids}

        for step in steps:
            if not isinstance(step, dict):
                continue
            sid = step.get("id", "")
            for dep in step.get("depends_on", []):
                if dep in step_ids:
                    in_degree[sid] += 1
                    dependents[dep].append(sid)

        queue = deque(sid for sid, deg in in_degree.items() if deg == 0)
        visited = 0
        while queue:
            node = queue.popleft()
            visited += 1
            for neighbor in dependents[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited != len(step_ids):
            errors.append("Circular dependency detected")

    return errors


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python tools/workflow_validator.py <workflow.json>", file=sys.stderr)
        return 1

    path = Path(sys.argv[1])
    errors = validate_workflow(path)

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    print(f"OK: {path.name} is valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
