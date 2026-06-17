"""
@name: Run Weather Pipeline
@type: script
@version: 1

Run this with:  python examples/weather_pipeline/run.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.engine.workflow import WorkflowEngine
from app.core.engine.function_runner import FilesystemFunctionRunner
from app.core.models.context import ExecutionContext
from app.core.models.request import HttpMethod, RequestDef
from app.ui.app import App


async def main():
    workflow_path = Path(__file__).parent / "workflow.json"
    with open(workflow_path) as f:
        data = json.load(f)

    from app.core.models.workflow import WorkflowDef, WorkflowStep, StepType, RetryConfig, RetryStrategy

    steps = []
    for s in data["steps"]:
        steps.append(WorkflowStep(
            id=s["id"],
            name=s.get("name", s["id"]),
            step_type=StepType(s["type"]),
            config=s.get("config", {}),
            depends_on=s.get("depends_on", []),
            output_variable=s.get("output_variable"),
        ))

    workflow = WorkflowDef(
        id=data["id"],
        name=data["name"],
        description=data.get("description", ""),
        steps=steps,
        variables=data.get("variables", {}),
    )

    async with App(":memory:") as app:
        engine = WorkflowEngine(request_executor=app.request_executor, event_bus=app.event_bus)
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

        export = ctx.metadata.get("export_result")
        if export:
            print(f"\n  Results:")
            print(f"  {json.dumps(export['record'], indent=4)}")
            print(f"\n  Exported to:")
            print(f"    JSON: {export['json']}")
            print(f"    CSV:  {export['csv']}")
        else:
            print("\n  No export generated (pipeline may have failed)")

        print(f"\n{'='*60}")
        status = "PASSED" if result.success else "FAILED"
        print(f"  {status} in {result.total_duration_ms}ms")
        print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
