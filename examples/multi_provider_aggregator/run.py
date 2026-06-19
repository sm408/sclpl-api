"""Multi-Provider Aggregator - Run with: python examples/multi_provider_aggregator/run.py"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.utils import load_workflow, run_workflow, print_result


async def main():
    workflow = load_workflow(Path(__file__).parent / "workflow.json")
    result, ctx = await run_workflow(workflow)
    print_result(result, ctx)

    # Print comparison report if available
    report_raw = ctx.workflow_variables.get("final_report")
    if report_raw:
        try:
            report = json.loads(report_raw) if isinstance(report_raw, str) else report_raw
            summary = report.get("executive_summary", {})
            print(f"\n  Providers: {summary.get('total_providers', 0)}")
            print(f"  Completion Rate: {summary.get('overall_completion_rate', 0)}%")
        except (json.JSONDecodeError, TypeError):
            pass


if __name__ == "__main__":
    asyncio.run(main())
