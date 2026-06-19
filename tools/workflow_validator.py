"""
Workflow Validator for SCLPLAPI

Validates workflow.json files for:
- Circular dependency detection
- Function reference verification
- Missing variable reporting
- Step type validation

Usage:
    python tools/workflow_validator.py <workflow.json> [--functions-dir functions]
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict, deque
from pathlib import Path


class ValidationResult:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []

    @property
    def valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, msg: str) -> None:
        self.errors.append(f"ERROR: {msg}")

    def add_warning(self, msg: str) -> None:
        self.warnings.append(f"WARN:  {msg}")

    def add_info(self, msg: str) -> None:
        self.info.append(f"INFO:  {msg}")

    def report(self) -> str:
        lines: list[str] = []
        if self.errors:
            lines.extend(self.errors)
        if self.warnings:
            lines.extend(self.warnings)
        if self.info:
            lines.extend(self.info)
        if not lines:
            lines.append("OK: Workflow is valid")
        return "\n".join(lines)


def load_workflow(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_required_fields(data: dict, result: ValidationResult) -> None:
    if "id" not in data or not data["id"]:
        result.add_error("Missing or empty 'id' field")
    if "name" not in data or not data["name"]:
        result.add_warning("Missing or empty 'name' field")
    if "steps" not in data:
        result.add_error("Missing 'steps' array")
    elif not isinstance(data["steps"], list):
        result.add_error("'steps' must be an array")
    elif len(data["steps"]) == 0:
        result.add_warning("Workflow has no steps")


def detect_cycles(steps: list[dict], result: ValidationResult) -> None:
    graph: dict[str, list[str]] = defaultdict(list)
    for step in steps:
        sid = step.get("id", "")
        for dep in step.get("depends_on", []):
            graph[dep].append(sid)

    step_ids = {s.get("id") for s in steps}
    in_degree: dict[str, int] = {sid: 0 for sid in step_ids}
    for step in steps:
        for dep in step.get("depends_on", []):
            if dep in step_ids:
                in_degree[step["id"]] += 1

    queue = deque(sid for sid, deg in in_degree.items() if deg == 0)
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited < len(step_ids):
        cycle_nodes = [sid for sid, deg in in_degree.items() if deg > 0]
        result.add_error(f"Circular dependency detected involving steps: {', '.join(cycle_nodes)}")


def check_duplicate_ids(steps: list[dict], result: ValidationResult) -> None:
    seen: dict[str, int] = {}
    for step in steps:
        sid = step.get("id", "")
        if sid in seen:
            result.add_error(f"Duplicate step id: '{sid}'")
        seen[sid] = seen.get(sid, 0) + 1


def check_missing_dependencies(steps: list[dict], result: ValidationResult) -> None:
    step_ids = {s.get("id") for s in steps}
    for step in steps:
        sid = step.get("id", "")
        for dep in step.get("depends_on", []):
            if dep not in step_ids:
                result.add_error(f"Step '{sid}' depends on unknown step '{dep}'")


def check_step_types(steps: list[dict], result: ValidationResult) -> None:
    valid_types = {"request", "function", "transformer", "export", "delay"}
    for step in steps:
        sid = step.get("id", "")
        stype = step.get("type", "")
        if stype not in valid_types:
            result.add_error(f"Step '{sid}' has invalid type '{stype}' (expected: {', '.join(sorted(valid_types))})")
        if stype == "request":
            config = step.get("config", {})
            inline = config.get("inline_request")
            if not inline:
                result.add_warning(f"Request step '{sid}' has no 'config.inline_request'")
            elif not inline.get("url"):
                result.add_error(f"Request step '{sid}' has empty URL")
        if stype == "function":
            config = step.get("config", {})
            if not config.get("function_name"):
                result.add_error(f"Function step '{sid}' has no 'config.function_name'")


def check_function_references(steps: list[dict], functions_dir: str, result: ValidationResult) -> None:
    from app.core.engine.function_runner import FilesystemFunctionRunner

    runner = FilesystemFunctionRunner(functions_dir)
    discovered = runner.discover()
    known_names = {f.get("name") for f in discovered if f.get("name")}

    for step in steps:
        if step.get("type") == "function":
            fname = step.get("config", {}).get("function_name", "")
            if fname and fname not in known_names:
                result.add_warning(
                    f"Step '{step.get('id')}' references function '{fname}' "
                    f"not found in {functions_dir}/"
                )


def check_variables(steps: list[dict], variables: dict[str, str], result: ValidationResult) -> None:
    import re

    var_pattern = re.compile(r"\{\{(\w+)\}\}")
    declared_vars = set(variables.keys())
    used_vars: set[str] = set()

    for step in steps:
        config = step.get("config", {})
        inline = config.get("inline_request", {})
        url = inline.get("url", "")
        for m in var_pattern.finditer(url):
            used_vars.add(m.group(1))
        body = inline.get("body", "")
        if isinstance(body, str):
            for m in var_pattern.finditer(body):
                used_vars.add(m.group(1))

    undeclared = used_vars - declared_vars
    if undeclared:
        result.add_warning(f"Variables used but not declared in workflow: {', '.join(sorted(undeclared))}")

    unused = declared_vars - used_vars
    unused.discard("base_url")
    if unused:
        result.add_info(f"Variables declared but not used in steps: {', '.join(sorted(unused))}")


def validate_workflow(path: Path, functions_dir: str = "functions") -> ValidationResult:
    result = ValidationResult()

    if not path.exists():
        result.add_error(f"File not found: {path}")
        return result

    try:
        data = load_workflow(path)
    except json.JSONDecodeError as e:
        result.add_error(f"Invalid JSON: {e}")
        return result

    check_required_fields(data, result)

    steps = data.get("steps", [])
    if not isinstance(steps, list):
        return result

    check_duplicate_ids(steps, result)
    check_missing_dependencies(steps, result)
    detect_cycles(steps, result)
    check_step_types(steps, result)
    check_function_references(steps, functions_dir, result)
    check_variables(steps, data.get("variables", {}), result)

    result.add_info(f"Workflow '{data.get('id', '?')}': {len(steps)} steps")
    return result


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    path = Path(sys.argv[1])
    functions_dir = "functions"
    if "--functions-dir" in sys.argv:
        idx = sys.argv.index("--functions-dir")
        if idx + 1 < len(sys.argv):
            functions_dir = sys.argv[idx + 1]

    result = validate_workflow(path, functions_dir)
    print(result.report())
    sys.exit(0 if result.valid else 1)


if __name__ == "__main__":
    main()
