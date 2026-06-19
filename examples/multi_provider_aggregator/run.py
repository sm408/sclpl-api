"""
@name: Run Multi-Provider Aggregator
@type: script
@version: 1

Run this with:  python examples/multi_provider_aggregator/run.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.engine.parallel_workflow import ParallelWorkflowEngine
from app.core.models.context import ExecutionContext
from app.core.models.workflow import WorkflowDef, WorkflowStep, StepType
from app.ui.app import App


def load_workflow(path):
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


async def main():
    workflow = load_workflow(Path(__file__).parent / "workflow.json")

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

        # Print step results
        for sr in result.step_results:
            icon = "OK" if sr.success else "FAIL"
            print(f"  [{icon}] {sr.step_name}  ({sr.duration_ms}ms)")
            if sr.error:
                print(f"        Error: {sr.error}")

        print(f"\n{'='*60}")

        # Print the final comparison report
        report_raw = ctx.workflow_variables.get("final_report")
        if report_raw:
            try:
                report = json.loads(report_raw) if isinstance(report_raw, str) else report_raw
                print("\n  Comparison Report:")
                print(f"  {'-'*56}")
                summary = report.get("executive_summary", {})
                print(f"  Providers:          {summary.get('total_providers', 0)}")
                print(f"  Content Items:      {summary.get('total_content_items', 0)}")
                print(f"  Tasks:              {summary.get('total_tasks', 0)}")
                print(f"  Completion Rate:    {summary.get('overall_completion_rate', 0)}%")
                print(f"  Avg Posts/User:     {summary.get('avg_posts_per_user', 0)}")
                print(f"  Unique Cities:      {summary.get('unique_cities', 0)}")
                print(f"  Unique Companies:   {summary.get('unique_companies', 0)}")

                insights = report.get("cross_source_insights", [])
                if insights:
                    print(f"\n  Insights:")
                    for insight in insights:
                        print(f"    - {insight}")

                # Save report to output
                output_dir = Path(__file__).parent / "output"
                output_dir.mkdir(exist_ok=True)
                report_path = output_dir / "comparison_report.json"
                with open(report_path, "w") as f:
                    json.dump(report, f, indent=2)
                print(f"\n  Report saved to: {report_path}")

            except (json.JSONDecodeError, TypeError):
                print(f"\n  Raw report: {report_raw[:200]}...")
        else:
            print("\n  No report generated (pipeline may have failed)")

        print(f"\n{'='*60}")
        status = "PASSED" if result.success else "FAILED"
        print(f"  {status} in {result.total_duration_ms}ms")
        print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
