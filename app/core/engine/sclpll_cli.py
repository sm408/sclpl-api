"""
SCLPLL Compiler CLI

Usage:
    python -m app.core.engine.sclpll_cli compile <input.sclpll> [--output-dir <dir>]
    python -m app.core.engine.sclpll_cli decompile <workflow.json> [--output <output.sclpll>]
    python -m app.core.engine.sclpll_cli validate <input.sclpll>
    python -m app.core.engine.sclpll_cli run <input.sclpll>
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from app.core.engine.sclpll_compiler import SCLPLLCompiler, SCLPLLParseError


def compile_sclpll(input_path: str, output_dir: str | None = None) -> None:
    source = Path(input_path).read_text(encoding="utf-8")
    compiler = SCLPLLCompiler()

    try:
        workflow = compiler.parse(source)
    except SCLPLLParseError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(output_dir) if output_dir else Path(input_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "workflow.json"
    json_path.write_text(json.dumps(workflow, indent=2), encoding="utf-8")
    print(f"  Written: {json_path}")

    py_content = compiler.compile_to_py(source)
    py_path = out_dir / "run.py"
    py_path.write_text(py_content, encoding="utf-8")
    print(f"  Written: {py_path}")

    print(f"  Compiled {input_path} -> {out_dir}")


def decompile_json(input_path: str, output_path: str | None = None) -> None:
    source = Path(input_path).read_text(encoding="utf-8")
    compiler = SCLPLLCompiler()

    try:
        sclpll = compiler.decompile_json_to_sclpll(source)
    except (json.JSONDecodeError, SCLPLLParseError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    out_path = output_path or str(Path(input_path).with_suffix(".sclpll"))
    Path(out_path).write_text(sclpll, encoding="utf-8")
    print(f"  Written: {out_path}")


def validate_sclpll(input_path: str) -> None:
    source = Path(input_path).read_text(encoding="utf-8")
    compiler = SCLPLLCompiler()

    try:
        workflow = compiler.parse(source)
        print(f"  Valid: {workflow['id']} ({len(workflow['steps'])} steps)")
        for step in workflow["steps"]:
            deps = step.get("depends_on", [])
            dep_str = f" <- {', '.join(deps)}" if deps else ""
            out = step.get("output_variable", "")
            out_str = f" -> {out}" if out else ""
            print(f"    {step['id']}{dep_str}{out_str} [{step['type']}]")
    except SCLPLLParseError as e:
        print(f"Validation error: {e}", file=sys.stderr)
        sys.exit(1)


async def run_sclpll(input_path: str) -> None:
    source = Path(input_path).read_text(encoding="utf-8")
    compiler = SCLPLLCompiler()

    try:
        workflow_dict = compiler.parse(source)
    except SCLPLLParseError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        sys.exit(1)

    from app.core.engine.parallel_workflow import ParallelWorkflowEngine
    from app.core.models.context import ExecutionContext
    from app.core.models.workflow import WorkflowDef, WorkflowStep, StepType
    from app.ui.app import App

    steps = []
    for s in workflow_dict["steps"]:
        steps.append(WorkflowStep(
            id=s["id"], name=s.get("name", s["id"]),
            step_type=StepType(s["type"]), config=s.get("config", {}),
            depends_on=s.get("depends_on", []),
            output_variable=s.get("output_variable"),
        ))

    workflow = WorkflowDef(
        id=workflow_dict["id"], name=workflow_dict["name"],
        description=workflow_dict.get("description", ""),
        steps=steps, variables=workflow_dict.get("variables", {}),
    )

    async with App(":memory:") as app:
        engine = ParallelWorkflowEngine(
            request_executor=app.request_executor,
            event_bus=app.event_bus,
        )
        ctx = ExecutionContext()

        print(f"{'='*60}")
        print(f"  {workflow.name}")
        print(f"{'='*60}\n")

        result = await engine.execute(workflow, ctx, {})

        for sr in result.step_results:
            icon = "OK" if sr.success else "FAIL"
            print(f"  [{icon}] {sr.step_name}  ({sr.duration_ms}ms)")
            if sr.error:
                print(f"        Error: {sr.error}")

        print(f"\n{'='*60}")
        status = "PASSED" if result.success else "FAILED"
        print(f"  {status} in {result.total_duration_ms}ms")
        print(f"{'='*60}")


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    input_path = sys.argv[2]

    if command == "compile":
        output_dir = None
        if "--output-dir" in sys.argv:
            idx = sys.argv.index("--output-dir")
            output_dir = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        compile_sclpll(input_path, output_dir)

    elif command == "decompile":
        output_path = None
        if "--output" in sys.argv:
            idx = sys.argv.index("--output")
            output_path = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        decompile_json(input_path, output_path)

    elif command == "validate":
        validate_sclpll(input_path)

    elif command == "run":
        asyncio.run(run_sclpll(input_path))

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
