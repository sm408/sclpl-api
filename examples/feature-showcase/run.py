"""
SCLPLAPI Feature Showcase - Run with: python examples/feature-showcase/run.py

Demonstrates ALL SCLPLL features in a single workflow.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.utils import load_workflow, run_workflow


async def main():
    workflow = load_workflow(Path(__file__).parent / "workflow.json")
    result, ctx = await run_workflow(workflow)

    # Print step results
    print(f"\n{'=' * 60}")
    print(f"  {workflow.name}")
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
    print(f"{'=' * 60}")

    # Print the final report
    report_raw = ctx.workflow_variables.get("final_report")
    if report_raw:
        try:
            report = json.loads(report_raw) if isinstance(report_raw, str) else report_raw
            print(f"\n{'=' * 60}")
            print("  FINAL REPORT")
            print(f"{'=' * 60}\n")
            print(json.dumps(report, indent=2))
        except (json.JSONDecodeError, TypeError):
            print(f"\n  Raw report: {str(report_raw)[:200]}...")
    else:
        print("\n  No report generated")


if __name__ == "__main__":
    asyncio.run(main())
