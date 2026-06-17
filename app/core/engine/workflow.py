from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.contracts.event_bus import EventBus, Event
from app.core.engine.event_bus import SimpleEventBus
from app.core.engine.hooks import FunctionHookRunner
from app.core.engine.variable_resolver import DefaultVariableResolver
from app.core.models.context import ExecutionContext
from app.core.models.history import HistoryEntry, RunStatus
from app.core.models.request import RequestDef
from app.core.models.workflow import WorkflowDef, WorkflowStep, StepType
from app.services.request_executor import HttpRequestExecutor

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    step_id: str
    step_name: str
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: int = 0


@dataclass
class WorkflowResult:
    workflow_id: str
    workflow_name: str
    success: bool
    step_results: list[StepResult] = field(default_factory=list)
    total_duration_ms: int = 0
    error: str | None = None


class WorkflowEngine:
    def __init__(
        self,
        request_executor: HttpRequestExecutor | None = None,
        hook_runner: FunctionHookRunner | None = None,
        variable_resolver: DefaultVariableResolver | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._executor = request_executor or HttpRequestExecutor()
        self._hooks = hook_runner or FunctionHookRunner()
        self._resolver = variable_resolver or DefaultVariableResolver()
        self._event_bus = event_bus or SimpleEventBus()

    async def execute(
        self,
        workflow: WorkflowDef,
        ctx: ExecutionContext,
        requests: dict[str, RequestDef] | None = None,
    ) -> WorkflowResult:
        import time

        requests = requests or {}
        start = time.monotonic()
        step_results: list[StepResult] = []

        ctx.workflow_variables = dict(workflow.variables)

        self._event_bus.publish(Event(
            name="workflow.started",
            data={"workflow_id": workflow.id, "workflow_name": workflow.name},
        ))

        sorted_steps = self._topological_sort(workflow.steps)

        for step in sorted_steps:
            if not self._check_condition(step, ctx):
                step_results.append(StepResult(
                    step_id=step.id, step_name=step.name, success=True, output="skipped"
                ))
                continue

            step_result = await self._execute_step(step, ctx, requests)
            step_results.append(step_result)

            if step.output_variable and step_result.success:
                ctx.workflow_variables[step.output_variable] = str(step_result.output)
                ctx.step_outputs[step.id] = step_result.output

            if not step_result.success and step.retry.max_retries > 0:
                step_result = await self._retry_step(step, ctx, requests)
                step_results[-1] = step_result

            if not step_result.success:
                self._event_bus.publish(Event(
                    name="workflow.step_failed",
                    data={"step_id": step.id, "error": step_result.error},
                ))

        total_ms = int((time.monotonic() - start) * 1000)
        all_success = all(r.success for r in step_results)

        result = WorkflowResult(
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            success=all_success,
            step_results=step_results,
            total_duration_ms=total_ms,
        )

        self._event_bus.publish(Event(
            name="workflow.completed",
            data={"workflow_id": workflow.id, "success": all_success, "duration_ms": total_ms},
        ))

        return result

    async def _execute_step(
        self,
        step: WorkflowStep,
        ctx: ExecutionContext,
        requests: dict[str, RequestDef],
    ) -> StepResult:
        import time

        start = time.monotonic()

        try:
            if step.step_type == StepType.REQUEST:
                return await self._execute_request_step(step, ctx, requests, start)
            elif step.step_type == StepType.FUNCTION:
                return await self._execute_function_step(step, ctx, start)
            elif step.step_type == StepType.DELAY:
                import asyncio
                delay_s = step.config.get("delay_ms", 1000) / 1000
                await asyncio.sleep(delay_s)
                elapsed = int((time.monotonic() - start) * 1000)
                return StepResult(step_id=step.id, step_name=step.name, success=True, duration_ms=elapsed)
            else:
                return StepResult(
                    step_id=step.id, step_name=step.name, success=False,
                    error=f"Unsupported step type: {step.step_type}"
                )
        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            return StepResult(
                step_id=step.id, step_name=step.name, success=False,
                error=str(exc), duration_ms=elapsed
            )

    async def _execute_request_step(
        self,
        step: WorkflowStep,
        ctx: ExecutionContext,
        requests: dict[str, RequestDef],
        start: float,
    ) -> StepResult:
        request_id = step.request_id or step.config.get("request_id")
        request = requests.get(request_id) if request_id else None
        if not request:
            return StepResult(
                step_id=step.id, step_name=step.name, success=False,
                error=f"Request not found: {request_id}"
            )

        ctx = await self._hooks.run_pre_request(ctx)
        result, history = await self._executor.execute_with_history(request, ctx)

        response_ctx = ExecutionContext(
            request=request,
            environment=ctx.environment,
            variables=dict(ctx.variables),
            step_outputs=dict(ctx.step_outputs),
            workflow_variables=dict(ctx.workflow_variables),
        )
        response_ctx.metadata["response"] = result
        await self._hooks.run_post_response(response_ctx)

        elapsed = int((time.monotonic() - start) * 1000)

        if result.error:
            return StepResult(
                step_id=step.id, step_name=step.name, success=False,
                error=result.error, duration_ms=elapsed
            )

        return StepResult(
            step_id=step.id, step_name=step.name, success=True,
            output={"status_code": result.status_code, "body": result.body[:1000]},
            duration_ms=elapsed,
        )

    async def _execute_function_step(
        self,
        step: WorkflowStep,
        ctx: ExecutionContext,
        start: float,
    ) -> StepResult:
        from app.core.engine.function_runner import FilesystemFunctionRunner

        runner = FilesystemFunctionRunner()
        name = step.function_name or step.config.get("function_name", "")
        result = await runner.run(name, ctx)
        elapsed = int((time.monotonic() - start) * 1000)

        return StepResult(
            step_id=step.id, step_name=step.name, success=result.success,
            output=result.return_value, error=result.error, duration_ms=elapsed,
        )

    async def _retry_step(
        self,
        step: WorkflowStep,
        ctx: ExecutionContext,
        requests: dict[str, RequestDef],
    ) -> StepResult:
        import asyncio

        last_result: StepResult | None = None
        for attempt in range(step.retry.max_retries):
            delay_s = step.retry.delay_ms / 1000
            if step.retry.strategy.value == "exponential":
                delay_s *= (2 ** attempt)
            await asyncio.sleep(delay_s)

            last_result = await self._execute_step(step, ctx, requests)
            if last_result.success:
                return last_result

        return last_result or StepResult(
            step_id=step.id, step_name=step.name, success=False, error="Retry failed"
        )

    def _check_condition(self, step: WorkflowStep, ctx: ExecutionContext) -> bool:
        if not step.condition:
            return True
        try:
            resolved = self._resolver.resolve(step.condition, ctx)
            return bool(eval(resolved, {"__builtins__": {}}, {"ctx": ctx, "vars": ctx.workflow_variables}))
        except Exception:
            return True

    def _topological_sort(self, steps: list[WorkflowStep]) -> list[WorkflowStep]:
        step_map = {s.id: s for s in steps}
        visited: set[str] = set()
        result: list[WorkflowStep] = []

        def visit(step_id: str) -> None:
            if step_id in visited:
                return
            visited.add(step_id)
            step = step_map.get(step_id)
            if not step:
                return
            for dep_id in step.depends_on:
                visit(dep_id)
            result.append(step)

        for step in steps:
            visit(step.id)

        return result
