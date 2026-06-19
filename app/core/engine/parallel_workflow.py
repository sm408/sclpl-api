"""
@name: Parallel Workflow Engine
@type: engine
@version: 1

Enhanced workflow engine that supports parallel execution of independent steps.
Steps without dependencies run concurrently. Steps with dependencies wait for
all their dependencies to complete before executing.
"""

from __future__ import annotations

import asyncio
import logging
import operator
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.core.contracts.event_bus import EventBus, Event
from app.core.engine.event_bus import SimpleEventBus
from app.core.engine.hooks import FunctionHookRunner
from app.core.engine.variable_resolver import DefaultVariableResolver
from app.core.models.context import ExecutionContext
from app.core.models.history import HistoryEntry, RunStatus
from app.core.models.request import HttpMethod, RequestDef, RequestParam
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
    started_at: float = 0.0
    completed_at: float = 0.0


@dataclass
class WorkflowResult:
    workflow_id: str
    workflow_name: str
    success: bool
    step_results: list[StepResult] = field(default_factory=list)
    history_entries: list[HistoryEntry] = field(default_factory=list)
    total_duration_ms: int = 0
    parallel_groups: list[list[str]] = field(default_factory=list)
    error: str | None = None


class ParallelWorkflowEngine:
    """Workflow engine that executes independent steps in parallel.
    
    Execution strategy:
    1. Build dependency graph
    2. Find steps with no unmet dependencies (ready set)
    3. Execute ready set concurrently
    4. Mark completed steps, find new ready set
    5. Repeat until all steps complete or fail
    """

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
        self._semaphores: dict[int, asyncio.Semaphore] = {}

    async def execute(
        self,
        workflow: WorkflowDef,
        ctx: ExecutionContext,
        requests: dict[str, RequestDef] | None = None,
    ) -> WorkflowResult:
        requests = requests or {}
        start = time.monotonic()
        step_results: list[StepResult] = []
        history_entries: list[HistoryEntry] = []
        parallel_groups: list[list[str]] = []

        ctx.workflow_variables = dict(workflow.variables)

        self._event_bus.publish(Event(
            name="workflow.started",
            data={"workflow_id": workflow.id, "workflow_name": workflow.name},
        ))

        # Build dependency graph
        step_map = {s.id: s for s in workflow.steps}
        completed: set[str] = set()
        failed: set[str] = set()
        results_by_id: dict[str, StepResult] = {}

        # Track what each step depends on
        remaining_deps: dict[str, set[str]] = {}
        for step in workflow.steps:
            remaining_deps[step.id] = set(step.depends_on)

        total_steps = len(workflow.steps)

        while len(completed) + len(failed) < total_steps:
            # Find ready steps (all deps satisfied, not yet executed)
            ready = []
            for step_id, deps in remaining_deps.items():
                if step_id in completed or step_id in failed:
                    continue
                if deps.issubset(completed):
                    ready.append(step_id)

            if not ready:
                # Deadlock or all remaining steps have failed deps
                for step_id in remaining_deps:
                    if step_id not in completed and step_id not in failed:
                        failed.add(step_id)
                        step_results.append(StepResult(
                            step_id=step_id,
                            step_name=step_map[step_id].name,
                            success=False,
                            error="Dependency not satisfied (upstream failure)",
                        ))
                break

            parallel_groups.append(ready)
            logger.info(f"Executing parallel group: {ready}")

            # Execute ready steps concurrently
            tasks = []
            for step_id in ready:
                step = step_map[step_id]
                task = asyncio.create_task(
                    self._execute_step_safe(step, ctx, requests)
                )
                tasks.append((step_id, step, task))

            # Wait for all tasks in this group
            for step_id, step, task in tasks:
                step_result = await task
                step_results.append(step_result)
                results_by_id[step_id] = step_result

                if step_result.success:
                    completed.add(step_id)
                    ctx.step_outputs[step_id] = step_result.output

                    # Merge function output into context
                    if isinstance(step_result.output, ExecutionContext):
                        fn_ctx = step_result.output
                        ctx.workflow_variables.update(fn_ctx.workflow_variables)
                        ctx.step_outputs.update(fn_ctx.step_outputs)
                        ctx.metadata.update(fn_ctx.metadata)
                    elif step.output_variable:
                        # Only store as output variable if not an ExecutionContext
                        ctx.workflow_variables[step.output_variable] = str(step_result.output)
                else:
                    failed.add(step_id)
                    self._event_bus.publish(Event(
                        name="workflow.step_failed",
                        data={"step_id": step_id, "error": step_result.error},
                    ))

        total_ms = int((time.monotonic() - start) * 1000)
        all_success = len(failed) == 0

        result = WorkflowResult(
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            success=all_success,
            step_results=step_results,
            history_entries=history_entries,
            total_duration_ms=total_ms,
            parallel_groups=parallel_groups,
        )

        self._event_bus.publish(Event(
            name="workflow.completed",
            data={"workflow_id": workflow.id, "success": all_success, "duration_ms": total_ms},
        ))

        return result

    async def _execute_step_safe(
        self,
        step: WorkflowStep,
        ctx: ExecutionContext,
        requests: dict[str, RequestDef],
    ) -> StepResult:
        """Execute a step with error handling, timing, semaphore, foreach/repeat."""
        start = time.monotonic()

        try:
            if not self._check_condition(step, ctx):
                elapsed = int((time.monotonic() - start) * 1000)
                return StepResult(
                    step_id=step.id, step_name=step.name, success=True,
                    output="skipped", duration_ms=elapsed,
                    started_at=start, completed_at=time.monotonic(),
                )

            if step.foreach_collection:
                return await self._execute_foreach(step, ctx, requests, start)

            if step.repeat_count is not None and step.repeat_count > 0:
                return await self._execute_repeat(step, ctx, requests, start)

            sem = self._get_semaphore(step)
            if sem:
                async with sem:
                    result, entry = await self._execute_step(step, ctx, requests)
            else:
                result, entry = await self._execute_step(step, ctx, requests)

            result.started_at = start
            result.completed_at = time.monotonic()
            return result

        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            return StepResult(
                step_id=step.id, step_name=step.name, success=False,
                error=str(exc), duration_ms=elapsed,
                started_at=start, completed_at=time.monotonic(),
            )

    async def _execute_step(
        self,
        step: WorkflowStep,
        ctx: ExecutionContext,
        requests: dict[str, RequestDef],
    ) -> tuple[StepResult, HistoryEntry | None]:
        start = time.monotonic()

        if step.step_type == StepType.REQUEST:
            return await self._execute_request_step(step, ctx, requests, start)
        elif step.step_type == StepType.FUNCTION:
            return await self._execute_function_step(step, ctx, start)
        elif step.step_type == StepType.DELAY:
            delay_s = step.config.get("delay_ms", 1000) / 1000
            await asyncio.sleep(delay_s)
            elapsed = int((time.monotonic() - start) * 1000)
            return StepResult(step_id=step.id, step_name=step.name, success=True, duration_ms=elapsed), None
        else:
            return StepResult(
                step_id=step.id, step_name=step.name, success=False,
                error=f"Unsupported step type: {step.step_type}"
            ), None

    async def _execute_request_step(
        self,
        step: WorkflowStep,
        ctx: ExecutionContext,
        requests: dict[str, RequestDef],
        start: float,
    ) -> tuple[StepResult, HistoryEntry | None]:
        request = None

        merged_vars = {**ctx.variables, **ctx.workflow_variables, **ctx.batch_row}

        request_id = step.request_id or step.config.get("request_id")
        if request_id:
            request = requests.get(request_id)

        if not request:
            inline = step.config.get("inline_request")
            if inline:
                resolve_ctx = ExecutionContext(
                    environment=ctx.environment,
                    variables=merged_vars,
                    step_outputs=dict(ctx.step_outputs),
                    workflow_variables=dict(ctx.workflow_variables),
                )
                url = self._resolver.resolve(inline.get("url", ""), resolve_ctx)

                # Convert dict headers to list of RequestParam
                headers_dict = inline.get("headers", {})
                headers = []
                for k, v in headers_dict.items():
                    headers.append(RequestParam(
                        key=self._resolver.resolve(str(k), resolve_ctx),
                        value=self._resolver.resolve(str(v), resolve_ctx),
                        enabled=True,
                    ))

                body = inline.get("body")
                if body:
                    body = self._resolver.resolve(body, resolve_ctx)

                request = RequestDef(
                    id=f"inline-{step.id}",
                    name=step.name,
                    method=HttpMethod(inline.get("method", "GET").upper()),
                    url=url,
                    headers=headers,
                    body=body,
                )

        if not request:
            return StepResult(
                step_id=step.id, step_name=step.name, success=False,
                error=f"Request not found: {request_id}"
            ), None

        step_ctx = ExecutionContext(
            request=request,
            environment=ctx.environment,
            variables=merged_vars,
            step_outputs=dict(ctx.step_outputs),
            workflow_variables=dict(ctx.workflow_variables),
            batch_row=dict(ctx.batch_row),
            metadata=dict(ctx.metadata),
        )

        step_ctx = await self._hooks.run_pre_request(step_ctx)
        result, entry = await self._executor.execute_with_history(request, step_ctx)

        step_ctx.metadata["response"] = result
        await self._hooks.run_post_response(step_ctx)

        elapsed = int((time.monotonic() - start) * 1000)

        if result.error:
            return StepResult(
                step_id=step.id, step_name=step.name, success=False,
                error=result.error, duration_ms=elapsed
            ), entry

        return StepResult(
            step_id=step.id, step_name=step.name, success=True,
            output={"status_code": result.status_code, "body": result.body},
            duration_ms=elapsed,
        ), entry

    async def _execute_function_step(
        self,
        step: WorkflowStep,
        ctx: ExecutionContext,
        start: float,
    ) -> tuple[StepResult, None]:
        from app.core.engine.function_runner import FilesystemFunctionRunner

        runner = FilesystemFunctionRunner()
        name = step.function_name or step.config.get("function_name", "")
        result = await runner.run(name, ctx)
        elapsed = int((time.monotonic() - start) * 1000)

        return StepResult(
            step_id=step.id, step_name=step.name, success=result.success,
            output=result.return_value, error=result.error, duration_ms=elapsed,
        ), None

    def _check_condition(self, step: WorkflowStep, ctx: ExecutionContext) -> bool:
        if not step.condition:
            return True
        try:
            resolved = self._resolver.resolve(step.condition, ctx)
            ops = {"==": operator.eq, "!=": operator.ne, ">=": operator.ge,
                   "<=": operator.le, ">": operator.gt, "<": operator.lt}
            for op_str, op_func in ops.items():
                if op_str in resolved:
                    left, right = resolved.split(op_str, 1)
                    left, right = left.strip(), right.strip()
                    try:
                        left_n, right_n = float(left), float(right)
                        return op_func(left_n, right_n)
                    except (ValueError, TypeError):
                        if op_str in ("==", "!="):
                            return op_func(left, right)
                        return True
            return bool(eval(resolved, {"__builtins__": {}}, {"ctx": ctx, "vars": ctx.workflow_variables}))
        except Exception:
            return True

    def _get_semaphore(self, step: WorkflowStep) -> asyncio.Semaphore | None:
        if step.semaphore is None or step.semaphore < 1:
            return None
        if step.semaphore not in self._semaphores:
            self._semaphores[step.semaphore] = asyncio.Semaphore(step.semaphore)
        return self._semaphores[step.semaphore]

    async def _execute_foreach(
        self,
        step: WorkflowStep,
        ctx: ExecutionContext,
        requests: dict[str, RequestDef],
        start: float,
    ) -> StepResult:
        collection_expr = step.foreach_collection or ""
        resolved_collection = self._resolver.resolve(collection_expr, ctx)
        import json as _json
        try:
            items = _json.loads(resolved_collection)
        except (ValueError, TypeError):
            items = [resolved_collection]

        if not isinstance(items, list):
            items = [items]

        var_name = step.foreach_variable or "item"
        outputs: list[Any] = []
        errors: list[str] = []
        sem = self._get_semaphore(step)

        for idx, item in enumerate(items):
            loop_ctx = ExecutionContext(
                environment=ctx.environment,
                variables=dict(ctx.variables),
                step_outputs=dict(ctx.step_outputs),
                workflow_variables=dict(ctx.workflow_variables),
                batch_row=dict(ctx.batch_row),
                metadata=dict(ctx.metadata),
            )
            loop_ctx.workflow_variables[var_name] = _json.dumps(item) if isinstance(item, (dict, list)) else str(item)
            loop_ctx.workflow_variables["_index"] = str(idx)

            if sem:
                async with sem:
                    result, _ = await self._execute_step(step, loop_ctx, requests)
            else:
                result, _ = await self._execute_step(step, loop_ctx, requests)

            if result.success:
                outputs.append(result.output)
            else:
                errors.append(f"[{idx}] {result.error}")

        elapsed = int((time.monotonic() - start) * 1000)
        if errors:
            return StepResult(
                step_id=step.id, step_name=step.name, success=False,
                error="; ".join(errors), duration_ms=elapsed,
                started_at=start, completed_at=time.monotonic(),
            )
        return StepResult(
            step_id=step.id, step_name=step.name, success=True,
            output=outputs, duration_ms=elapsed,
            started_at=start, completed_at=time.monotonic(),
        )

    async def _execute_repeat(
        self,
        step: WorkflowStep,
        ctx: ExecutionContext,
        requests: dict[str, RequestDef],
        start: float,
    ) -> StepResult:
        count = step.repeat_count or 1
        outputs: list[Any] = []
        errors: list[str] = []
        sem = self._get_semaphore(step)

        for idx in range(count):
            loop_ctx = ExecutionContext(
                environment=ctx.environment,
                variables=dict(ctx.variables),
                step_outputs=dict(ctx.step_outputs),
                workflow_variables=dict(ctx.workflow_variables),
                batch_row=dict(ctx.batch_row),
                metadata=dict(ctx.metadata),
            )
            loop_ctx.workflow_variables["_index"] = str(idx)

            if sem:
                async with sem:
                    result, _ = await self._execute_step(step, loop_ctx, requests)
            else:
                result, _ = await self._execute_step(step, loop_ctx, requests)

            if result.success:
                outputs.append(result.output)
            else:
                errors.append(f"[{idx}] {result.error}")

        elapsed = int((time.monotonic() - start) * 1000)
        if errors:
            return StepResult(
                step_id=step.id, step_name=step.name, success=False,
                error="; ".join(errors), duration_ms=elapsed,
                started_at=start, completed_at=time.monotonic(),
            )
        return StepResult(
            step_id=step.id, step_name=step.name, success=True,
            output=outputs, duration_ms=elapsed,
            started_at=start, completed_at=time.monotonic(),
        )
