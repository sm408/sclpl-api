"""Shared workflow loading and execution utilities."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from app.core.engine.parallel_workflow import ParallelWorkflowEngine, WorkflowResult
from app.core.models.context import ExecutionContext
from app.core.models.workflow import WorkflowDef, WorkflowStep, StepType
from app.ui.app import App


def load_workflow(path: Path | str) -> WorkflowDef:
    """Load a workflow from a JSON file.

    Args:
        path: Path to workflow.json file

    Returns:
        WorkflowDef instance ready for execution
    """
    path = Path(path)
    with open(path) as f:
        data = json.load(f)

    steps = [
        WorkflowStep(
            id=s["id"],
            name=s.get("name", s["id"]),
            step_type=StepType(s["type"]),
            config=s.get("config", {}),
            depends_on=s.get("depends_on", []),
            output_variable=s.get("output_variable"),
            condition=s.get("condition"),
            semaphore=s.get("semaphore"),
            foreach_collection=s.get("foreach_collection"),
            foreach_variable=s.get("foreach_variable"),
            repeat_count=s.get("repeat_count"),
        )
        for s in data["steps"]
    ]

    return WorkflowDef(
        id=data["id"],
        name=data["name"],
        description=data.get("description", ""),
        steps=steps,
        variables=data.get("variables", {}),
    )


async def run_workflow(
    workflow: WorkflowDef,
    db_path: str = ":memory:",
) -> tuple[WorkflowResult, ExecutionContext]:
    """Execute a workflow and return results.

    Args:
        workflow: The workflow to execute
        db_path: Database path (default: in-memory)

    Returns:
        Tuple of (WorkflowResult, ExecutionContext)
    """
    async with App(db_path) as app:
        engine = ParallelWorkflowEngine(
            request_executor=app.request_executor,
            event_bus=app.event_bus,
        )
        ctx = ExecutionContext()
        result = await engine.execute(workflow, ctx, {})
        return result, ctx


def print_result(result: WorkflowResult, ctx: ExecutionContext | None = None) -> None:
    """Print workflow execution results in a formatted way.

    Args:
        result: The workflow execution result
        ctx: Optional execution context for printing report variables
    """
    print(f"\n{'=' * 60}")
    print(f"  {result.workflow_name}")
    print(f"{'=' * 60}\n")

    for sr in result.step_results:
        icon = "OK" if sr.success else "FAIL"
        label = "SKIPPED" if sr.output == "skipped" else f"{sr.duration_ms}ms"
        print(f"  [{icon}] {sr.step_name}  ({label})")
        if sr.error:
            print(f"        Error: {sr.error}")

    print(f"\n{'=' * 60}")
    status = "PASSED" if result.success else "FAILED"
    print(f"  {status} in {result.total_duration_ms}ms")
    print(f"  Parallel groups: {len(result.parallel_groups)}")

    if result.total_duration_ms > 0:
        sequential_time = sum(r.duration_ms for r in result.step_results)
        speedup = sequential_time / result.total_duration_ms
        print(f"  Speedup: {speedup:.1f}x faster than sequential")

    print(f"{'=' * 60}")


async def run_from_sclpll(
    sclpll_path: Path | str,
    db_path: str = ":memory:",
) -> tuple[WorkflowResult, ExecutionContext]:
    """Load and run a workflow from a .sclpll file.

    Args:
        sclpll_path: Path to the .sclpll file
        db_path: Database path (default: in-memory)

    Returns:
        Tuple of (WorkflowResult, ExecutionContext)
    """
    from app.core.engine.sclpll_compiler import SCLPLLCompiler

    sclpll_path = Path(sclpll_path)
    source = sclpll_path.read_text(encoding="utf-8")
    compiler = SCLPLLCompiler()
    workflow_dict = compiler.parse(source)

    steps = [
        WorkflowStep(
            id=s["id"],
            name=s.get("name", s["id"]),
            step_type=StepType(s["type"]),
            config=s.get("config", {}),
            depends_on=s.get("depends_on", []),
            output_variable=s.get("output_variable"),
            condition=s.get("condition"),
            semaphore=s.get("semaphore"),
            foreach_collection=s.get("foreach_collection"),
            foreach_variable=s.get("foreach_variable"),
            repeat_count=s.get("repeat_count"),
        )
        for s in workflow_dict["steps"]
    ]

    workflow = WorkflowDef(
        id=workflow_dict["id"],
        name=workflow_dict["name"],
        description=workflow_dict.get("description", ""),
        steps=steps,
        variables=workflow_dict.get("variables", {}),
    )

    return await run_workflow(workflow, db_path)
