from __future__ import annotations

import json
import re
import textwrap
from typing import Any


class SCLPLLParseError(Exception):
    def __init__(self, message: str, line_number: int, line: str) -> None:
        self.line_number = line_number
        self.line = line
        super().__init__(f"Line {line_number}: {message}\n  | {line}")


class SCLPLLCompiler:
    _DIRECTIVE_RE = re.compile(r"^@(\w+)\s*(.*)$")
    _COMMENT_RE = re.compile(r"^\s*#")
    _BLANK_RE = re.compile(r"^\s*$")
    _HEADER_RE = re.compile(r"^header\s+(.+?):\s*(.+)$")
    _REQUEST_RE = re.compile(r"^request\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(\S+)$", re.IGNORECASE)
    _FUNC_RE = re.compile(r"^func\s+(.+)$")
    _BODY_RE = re.compile(r"^body\s+(.+)$", re.DOTALL)
    _STEP_RE = re.compile(r"^@step\s+(\S+)(?:\s*<-\s*(.+?))?(?:\s*->\s*(\S+))?\s*$")
    _WORKFLOW_RE = re.compile(r'^@workflow\s+(\S+)\s*(?:"([^"]*)")?')
    _BASE_URL_RE = re.compile(r"^@base_url\s+(\S+)$")
    _VAR_RE = re.compile(r"^@var\s+(\S+)\s*=\s*(.+)$")
    _WHEN_RE = re.compile(r"^when\s+(.+?)\s*(==|!=|>=|<=|>|<)\s*(.+)$")
    _FOREACH_RE = re.compile(r"^foreach\s+(\{\{.+\}\})\s+as\s+(\w+)$")
    _REPEAT_RE = re.compile(r"^repeat\s+(\d+)$")
    _SEMAPHORE_RE = re.compile(r"^semaphore\s+(\d+)$")

    def parse(self, source: str) -> dict[str, Any]:
        lines = source.splitlines()
        workflow: dict[str, Any] = {
            "id": "",
            "name": "",
            "description": "",
            "steps": [],
            "variables": {},
        }
        current_step: dict[str, Any] | None = None
        workflow_seen = False
        expect_workflow_desc = False
        desc_parts: list[str] = []

        for line_num, raw_line in enumerate(lines, start=1):
            line = raw_line.rstrip()

            if self._BLANK_RE.match(line) or self._COMMENT_RE.match(line):
                if expect_workflow_desc and desc_parts:
                    workflow["description"] = " ".join(desc_parts)
                    desc_parts = []
                    expect_workflow_desc = False
                continue

            if not line.startswith(" ") and not line.startswith("\t"):
                if expect_workflow_desc and desc_parts:
                    workflow["description"] = " ".join(desc_parts)
                    desc_parts = []
                current_step = None

            if expect_workflow_desc and (line.startswith("    ") or line.startswith("\t")):
                desc_parts.append(line.strip())
                continue

            if desc_parts:
                workflow["description"] = " ".join(desc_parts)
                desc_parts = []
            expect_workflow_desc = False

            if current_step is not None and (line.startswith("    ") or line.startswith("\t")):
                self._parse_step_body(current_step, line.strip(), line_num, line)
                continue

            directive = self._DIRECTIVE_RE.match(line)
            if directive:
                expect_workflow_desc = False
                keyword, rest = directive.group(1), directive.group(2).strip()
                if keyword == "workflow":
                    if workflow_seen:
                        raise SCLPLLParseError("Duplicate @workflow directive", line_num, line)
                    m = self._WORKFLOW_RE.match(line)
                    if not m:
                        raise SCLPLLParseError(
                            'Invalid @workflow syntax. Expected: @workflow <id> ["name"]',
                            line_num, line,
                        )
                    workflow["id"] = m.group(1)
                    workflow["name"] = m.group(2) or m.group(1)
                    workflow_seen = True
                    expect_workflow_desc = True
                elif keyword == "base_url":
                    m = self._BASE_URL_RE.match(line)
                    if not m:
                        raise SCLPLLParseError("Invalid @base_url syntax", line_num, line)
                    workflow["variables"]["base_url"] = m.group(1)
                elif keyword == "var":
                    m = self._VAR_RE.match(line)
                    if not m:
                        raise SCLPLLParseError("Invalid @var syntax. Expected: @var name = value", line_num, line)
                    workflow["variables"][m.group(1)] = m.group(2).strip()
                elif keyword == "step":
                    m = self._STEP_RE.match(line)
                    if not m:
                        raise SCLPLLParseError("Invalid @step syntax", line_num, line)
                    step_id = m.group(1)
                    deps_raw = m.group(2)
                    output_var = m.group(3)
                    depends_on = []
                    if deps_raw:
                        depends_on = [d.strip() for d in deps_raw.split(",") if d.strip()]
                    current_step: dict[str, Any] = {
                        "id": step_id,
                        "name": step_id,
                        "type": "request",
                        "config": {},
                    }
                    if depends_on:
                        current_step["depends_on"] = depends_on
                    if output_var:
                        current_step["output_variable"] = output_var
                    workflow["steps"].append(current_step)
                else:
                    raise SCLPLLParseError(f"Unknown directive: @{keyword}", line_num, line)
                continue

            raise SCLPLLParseError("Unexpected line (not inside a step body or unknown directive)", line_num, line)

        # Flush any trailing description collected after @workflow
        if expect_workflow_desc and desc_parts:
            workflow["description"] = " ".join(desc_parts)

        if not workflow["id"]:
            raise SCLPLLParseError("Missing @workflow directive", 0, "")

        return workflow

    def _parse_step_body(
        self, step: dict[str, Any], content: str, line_num: int, raw_line: str,
    ) -> None:
        # Strip leading '@' so both '@when' and 'when' syntaxes are accepted
        if content.startswith("@"):
            content = content[1:]

        req_match = self._REQUEST_RE.match(content)
        if req_match:
            method = req_match.group(1).upper()
            url = req_match.group(2)
            step["type"] = "request"
            step["config"]["inline_request"] = {
                "method": method,
                "url": url,
                "headers": {},
            }
            return

        func_match = self._FUNC_RE.match(content)
        if func_match:
            step["type"] = "function"
            step["config"]["function_name"] = func_match.group(1).strip()
            return

        header_match = self._HEADER_RE.match(content)
        if header_match:
            hdr_name = header_match.group(1).strip()
            hdr_value = header_match.group(2).strip()
            inline = step["config"].setdefault("inline_request", {"method": "GET", "url": "", "headers": {}})
            headers = inline.setdefault("headers", {})
            headers[hdr_name] = hdr_value
            return

        body_match = self._BODY_RE.match(content)
        if body_match:
            inline = step["config"].setdefault("inline_request", {"method": "GET", "url": "", "headers": {}})
            inline["body"] = body_match.group(1).strip()
            return

        when_match = self._WHEN_RE.match(content)
        if when_match:
            left = when_match.group(1).strip()
            op = when_match.group(2)
            right = when_match.group(3).strip()
            step["condition"] = f"{left} {op} {right}"
            return

        foreach_match = self._FOREACH_RE.match(content)
        if foreach_match:
            step["foreach_collection"] = foreach_match.group(1)
            step["foreach_variable"] = foreach_match.group(2)
            return

        repeat_match = self._REPEAT_RE.match(content)
        if repeat_match:
            step["repeat_count"] = int(repeat_match.group(1))
            return

        semaphore_match = self._SEMAPHORE_RE.match(content)
        if semaphore_match:
            step["semaphore"] = int(semaphore_match.group(1))
            return

        raise SCLPLLParseError(f"Unknown step body syntax: {content}", line_num, raw_line)

    def compile_to_json(self, source: str) -> str:
        workflow = self.parse(source)
        return json.dumps(workflow, indent=2)

    def compile_to_py(self, source: str) -> str:
        self.parse(source)
        return textwrap.dedent("""\
            import asyncio, json, sys, time
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
            from app.core.engine.parallel_workflow import ParallelWorkflowEngine
            from app.core.models.context import ExecutionContext
            from app.core.models.workflow import WorkflowDef, WorkflowStep, StepType
            from app.ui.app import App

            def load_workflow(path):
                with open(path) as f:
                    data = json.load(f)
                steps = [WorkflowStep(id=s["id"], name=s.get("name", s["id"]), step_type=StepType(s["type"]), config=s.get("config", {}), depends_on=s.get("depends_on", []), output_variable=s.get("output_variable"), condition=s.get("condition"), semaphore=s.get("semaphore"), foreach_collection=s.get("foreach_collection"), foreach_variable=s.get("foreach_variable"), repeat_count=s.get("repeat_count")) for s in data["steps"]]
                return WorkflowDef(id=data["id"], name=data["name"], description=data.get("description", ""), steps=steps, variables=data.get("variables", {}))

            async def main():
                workflow = load_workflow(Path(__file__).parent / "workflow.json")
                async with App(":memory:") as app:
                    engine = ParallelWorkflowEngine(request_executor=app.request_executor, event_bus=app.event_bus)
                    ctx = ExecutionContext()
                    print(f"{'='*60}\\n  {workflow.name}\\n{'='*60}\\n")
                    result = await engine.execute(workflow, ctx, {})
                    for sr in result.step_results:
                        icon = "OK" if sr.success else "FAIL"
                        print(f"  [{icon}] {sr.step_name}  ({sr.duration_ms}ms)")
                        if sr.error: print(f"        Error: {sr.error}")
                    print(f"\\n{'='*60}\\n  {'PASSED' if result.success else 'FAILED'} in {result.total_duration_ms}ms\\n{'='*60}")

            if __name__ == "__main__":
                asyncio.run(main())
        """)

    def parse_source_diagnostics(self, source: str) -> dict[str, Any]:
        """Parse SCLPLL source with structured diagnostics.

        Returns a dict with:
        - success: bool
        - definition: dict | None
        - diagnostics: list of {line, column, severity, message}
        - source_hash: str
        """
        import hashlib

        source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
        diagnostics: list[dict[str, Any]] = []

        try:
            definition = self.parse(source)
            # Additional warnings
            for step in definition.get("steps", []):
                if step.get("type") == "request":
                    inline = step.get("config", {}).get("inline_request", {})
                    if not inline.get("url"):
                        diagnostics.append({
                            "line": 0,
                            "column": 0,
                            "severity": "warning",
                            "message": f"Step '{step.get('id', '?')}': request step has no URL",
                        })
            return {
                "success": True,
                "definition": definition,
                "diagnostics": diagnostics,
                "source_hash": source_hash,
            }
        except SCLPLLParseError as exc:
            diagnostics.append({
                "line": exc.line_number,
                "column": 0,
                "severity": "error",
                "message": str(exc),
            })
            return {
                "success": False,
                "definition": None,
                "diagnostics": diagnostics,
                "source_hash": source_hash,
            }
        except Exception as exc:
            diagnostics.append({
                "line": 0,
                "column": 0,
                "severity": "error",
                "message": str(exc),
            })
            return {
                "success": False,
                "definition": None,
                "diagnostics": diagnostics,
                "source_hash": source_hash,
            }

    def validate_preflight(self, definition: dict[str, Any]) -> dict[str, Any]:
        """Validate a workflow definition for execution readiness.

        Returns a dict with:
        - valid: bool
        - issues: list of {severity, message, path}
        """
        issues: list[dict[str, Any]] = []
        steps = definition.get("steps", [])
        step_ids = {s.get("id") for s in steps}

        # Missing step IDs
        for i, step in enumerate(steps):
            if not step.get("id"):
                issues.append({
                    "severity": "error",
                    "message": f"Step at index {i} is missing an 'id' field",
                    "path": f"steps[{i}].id",
                })

        # Broken dependency references
        for step in steps:
            sid = step.get("id", "")
            for dep in step.get("depends_on", []):
                if dep not in step_ids:
                    issues.append({
                        "severity": "error",
                        "message": f"Step '{sid}' depends on unknown step '{dep}'",
                        "path": f"steps.{sid}.depends_on",
                    })

        # Circular dependencies
        visited: set[str] = set()
        in_stack: set[str] = set()
        step_map = {s.get("id", ""): s for s in steps}

        def _detect_cycle(sid: str) -> bool:
            if sid in in_stack:
                return True
            if sid in visited:
                return False
            visited.add(sid)
            in_stack.add(sid)
            for dep in step_map.get(sid, {}).get("depends_on", []):
                if _detect_cycle(dep):
                    return True
            in_stack.discard(sid)
            return False

        for sid in step_ids:
            if sid and sid not in visited:
                if _detect_cycle(sid):
                    issues.append({
                        "severity": "error",
                        "message": f"Circular dependency detected involving step '{sid}'",
                        "path": f"steps.{sid}",
                    })

        # Check for missing workflow ID
        if not definition.get("id"):
            issues.append({
                "severity": "warning",
                "message": "Workflow definition is missing an 'id' field",
                "path": "id",
            })

        return {
            "valid": not any(i["severity"] == "error" for i in issues),
            "issues": issues,
        }

    def decompile_json_to_sclpll(self, json_str: str) -> str:
        data = json.loads(json_str)
        return self.decompile_dict_to_sclpll(data)

    def decompile_dict_to_sclpll(self, workflow_dict: dict[str, Any]) -> str:
        parts: list[str] = []

        wf_id = workflow_dict.get("id", "unnamed")
        wf_name = workflow_dict.get("name", "Unnamed Workflow")
        parts.append(f'@workflow {wf_id} "{wf_name}"')

        desc = workflow_dict.get("description", "").strip()
        if desc:
            parts.append(f"    {desc}")

        variables = workflow_dict.get("variables", {})
        base_url = variables.get("base_url")
        if base_url:
            parts.append("")
            parts.append(f"@base_url {base_url}")

        for var_name, var_value in sorted(variables.items()):
            if var_name == "base_url":
                continue
            parts.append(f"@var {var_name} = {var_value}")

        for step in workflow_dict.get("steps", []):
            parts.append("")
            step_line = f"@step {step['id']}"
            deps = step.get("depends_on", [])
            if deps:
                step_line += f" <- {', '.join(deps)}"
            output_var = step.get("output_variable")
            if output_var:
                step_line += f" -> {output_var}"
            parts.append(step_line)

            config = step.get("config", {})
            step_type = step.get("type", "request")

            condition = step.get("condition")
            if condition:
                parts.append(f"    @when {condition}")

            foreach_col = step.get("foreach_collection")
            foreach_var = step.get("foreach_variable")
            if foreach_col and foreach_var:
                parts.append(f"    @foreach {foreach_col} as {foreach_var}")

            repeat = step.get("repeat_count")
            if repeat is not None:
                parts.append(f"    @repeat {repeat}")

            sem = step.get("semaphore")
            if sem is not None:
                parts.append(f"    @semaphore {sem}")

            if step_type == "function":
                fn_name = config.get("function_name", "")
                parts.append(f"    func {fn_name}")
            elif step_type == "request":
                inline = config.get("inline_request", {})
                method = inline.get("method", "GET").upper()
                url = inline.get("url", "")
                parts.append(f"    request {method} {url}")

                headers = inline.get("headers", {})
                for hdr_name, hdr_value in sorted(headers.items()):
                    parts.append(f"    header {hdr_name}: {hdr_value}")

                body = inline.get("body")
                if body:
                    parts.append(f"    body {body}")

        return "\n".join(parts) + "\n"
