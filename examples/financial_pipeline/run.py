"""Financial Pipeline - Run with: python examples/financial_pipeline/run.py"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.utils import load_workflow, run_workflow, print_result


async def main():
    workflow = load_workflow(Path(__file__).parent / "workflow.json")
    result, ctx = await run_workflow(workflow)
    print_result(result, ctx)


if __name__ == "__main__":
    asyncio.run(main())
