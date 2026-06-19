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
    steps = [WorkflowStep(id=s["id"], name=s.get("name", s["id"]), step_type=StepType(s["type"]), config=s.get("config", {}), depends_on=s.get("depends_on", []), output_variable=s.get("output_variable")) for s in data["steps"]]
    return WorkflowDef(id=data["id"], name=data["name"], description=data.get("description", ""), steps=steps, variables=data.get("variables", {}))

async def main():
    workflow = load_workflow(Path(__file__).parent / "workflow.json")
    async with App(":memory:") as app:
        engine = ParallelWorkflowEngine(request_executor=app.request_executor, event_bus=app.event_bus)
        ctx = ExecutionContext()
        print(f"{'='*60}\n  {workflow.name}\n{'='*60}\n")
        result = await engine.execute(workflow, ctx, {})
        for sr in result.step_results:
            icon = "OK" if sr.success else "FAIL"
            print(f"  [{icon}] {sr.step_name}  ({sr.duration_ms}ms)")
            if sr.error: print(f"        Error: {sr.error}")
        print(f"\n{'='*60}\n  {'PASSED' if result.success else 'FAILED'} in {result.total_duration_ms}ms\n{'='*60}")

if __name__ == "__main__":
    asyncio.run(main())
