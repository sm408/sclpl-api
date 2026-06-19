from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from app.core.contracts.event_bus import Event
from app.core.contracts.request_executor import ResponseResult
from app.core.engine.event_bus import SimpleEventBus
from app.core.engine.parallel_workflow import ParallelWorkflowEngine, WorkflowResult
from app.core.models.context import ExecutionContext
from app.core.models.history import HistoryEntry, RunStatus
from app.core.models.request import HttpMethod, RequestDef, RequestParam
from app.core.models.workflow import StepType, WorkflowDef, WorkflowStep


def _make_request_step(step_id: str, url: str = "https://example.com", **kwargs) -> WorkflowStep:
    return WorkflowStep(
        id=step_id,
        name=step_id,
        step_type=StepType.REQUEST,
        config={"inline_request": {"method": "GET", "url": url, "headers": {}}},
        **kwargs,
    )


def _make_delay_step(step_id: str, delay_ms: int = 10, **kwargs) -> WorkflowStep:
    return WorkflowStep(
        id=step_id,
        name=step_id,
        step_type=StepType.DELAY,
        config={"delay_ms": delay_ms},
        **kwargs,
    )


def _mock_executor_response(status_code=200, body='{"ok": true}', error=None):
    result = ResponseResult(
        status_code=status_code,
        headers={"content-type": "application/json"},
        body=body,
        duration_ms=10,
        error=error,
    )
    entry = HistoryEntry(
        id="h1", request_id="r1", request_name="test",
        method="GET", url="https://example.com",
        status=RunStatus.SUCCESS if not error else RunStatus.ERROR,
        status_code=status_code, response_body=body, duration_ms=10,
        error_message=error,
    )
    return result, entry


def _make_engine(status_code=200, body='{"ok": true}', error=None):
    mock_executor = AsyncMock()
    mock_executor.execute_with_history = AsyncMock(
        return_value=_mock_executor_response(status_code, body, error)
    )
    mock_hooks = AsyncMock()
    mock_hooks.run_pre_request = AsyncMock(side_effect=lambda ctx: ctx)
    mock_hooks.run_post_response = AsyncMock(side_effect=lambda ctx: ctx)
    return ParallelWorkflowEngine(
        request_executor=mock_executor,
        hook_runner=mock_hooks,
    )


class TestParallelWorkflowExecute:
    """Tests for ParallelWorkflowEngine.execute() with parallel and sequential steps."""

    async def test_execute_single_step(self) -> None:
        """A single request step executes successfully."""
        engine = _make_engine()
        workflow = WorkflowDef(id="wf1", name="Test", steps=[_make_request_step("s1")])
        result = await engine.execute(workflow, ExecutionContext())
        assert result.success
        assert len(result.step_results) == 1

    async def test_execute_independent_steps_in_parallel(self) -> None:
        """Steps without dependencies run concurrently (same parallel group)."""
        engine = _make_engine()
        workflow = WorkflowDef(
            id="wf1", name="Test",
            steps=[_make_request_step("a"), _make_request_step("b"), _make_request_step("c")],
        )
        result = await engine.execute(workflow, ExecutionContext())
        assert result.success
        assert len(result.step_results) == 3
        # All three should be in a single parallel group
        assert len(result.parallel_groups) == 1
        assert set(result.parallel_groups[0]) == {"a", "b", "c"}

    async def test_execute_parallel_groups_with_dependencies(self) -> None:
        """Steps are grouped into parallel waves based on dependency resolution."""
        engine = _make_engine()
        workflow = WorkflowDef(
            id="wf1", name="Test",
            steps=[
                _make_request_step("a"),
                _make_request_step("b"),
                _make_request_step("c", depends_on=["a", "b"]),
            ],
        )
        result = await engine.execute(workflow, ExecutionContext())
        assert result.success
        assert len(result.parallel_groups) == 2
        assert set(result.parallel_groups[0]) == {"a", "b"}
        assert result.parallel_groups[1] == ["c"]

    async def test_execute_three_level_parallel_groups(self) -> None:
        """Three levels of dependencies produce three parallel groups."""
        engine = _make_engine()
        workflow = WorkflowDef(
            id="wf1", name="Test",
            steps=[
                _make_request_step("a"),
                _make_request_step("b"),
                _make_request_step("c", depends_on=["a"]),
                _make_request_step("d", depends_on=["b"]),
                _make_request_step("e", depends_on=["c", "d"]),
            ],
        )
        result = await engine.execute(workflow, ExecutionContext())
        assert result.success
        assert len(result.parallel_groups) == 3

    async def test_parallel_execution_is_faster(self) -> None:
        """Parallel steps finish in roughly the time of one step, not the sum."""
        call_times: list[float] = []

        async def slow_executor(request, ctx):
            call_times.append(time.monotonic())
            await asyncio.sleep(0.05)
            return _mock_executor_response()

        mock_executor = AsyncMock()
        mock_executor.execute_with_history = AsyncMock(side_effect=slow_executor)
        mock_hooks = AsyncMock()
        mock_hooks.run_pre_request = AsyncMock(side_effect=lambda ctx: ctx)
        mock_hooks.run_post_response = AsyncMock(side_effect=lambda ctx: ctx)
        engine = ParallelWorkflowEngine(request_executor=mock_executor, hook_runner=mock_hooks)

        workflow = WorkflowDef(
            id="wf1", name="Test",
            steps=[_make_request_step("a"), _make_request_step("b"), _make_request_step("c")],
        )
        start = time.monotonic()
        result = await engine.execute(workflow, ExecutionContext())
        elapsed = time.monotonic() - start
        assert result.success
        # Three 50ms steps in parallel should take ~50-100ms, not 150ms
        assert elapsed < 0.15


class TestParallelWorkflowFailure:
    """Tests for step failure handling in parallel workflows."""

    async def test_step_failure_marks_workflow_failed(self) -> None:
        """A failing step causes the overall workflow to report failure."""
        engine = _make_engine(error="boom")
        workflow = WorkflowDef(id="wf1", name="Test", steps=[_make_request_step("s1")])
        result = await engine.execute(workflow, ExecutionContext())
        assert not result.success
        assert result.step_results[0].error == "boom"

    async def test_failure_blocks_dependent_steps(self) -> None:
        """Steps depending on a failed step are marked with dependency failure."""
        call_count = 0

        async def selective_fail(request, ctx):
            nonlocal call_count
            call_count += 1
            url = request.url
            if "fail" in url:
                return _mock_executor_response(error="fail")
            return _mock_executor_response()

        mock_executor = AsyncMock()
        mock_executor.execute_with_history = AsyncMock(side_effect=selective_fail)
        mock_hooks = AsyncMock()
        mock_hooks.run_pre_request = AsyncMock(side_effect=lambda ctx: ctx)
        mock_hooks.run_post_response = AsyncMock(side_effect=lambda ctx: ctx)
        engine = ParallelWorkflowEngine(request_executor=mock_executor, hook_runner=mock_hooks)

        workflow = WorkflowDef(
            id="wf1", name="Test",
            steps=[
                _make_request_step("a", url="https://fail.com"),
                _make_request_step("b", depends_on=["a"]),
            ],
        )
        result = await engine.execute(workflow, ExecutionContext())
        assert not result.success
        b_result = next(sr for sr in result.step_results if sr.step_id == "b")
        assert not b_result.success
        assert "Dependency not satisfied" in (b_result.error or "")

    async def test_deadlock_detection(self) -> None:
        """Circular dependencies are detected and remaining steps fail."""
        engine = _make_engine()
        workflow = WorkflowDef(
            id="wf1", name="Test",
            steps=[
                _make_request_step("a", depends_on=["b"]),
                _make_request_step("b", depends_on=["a"]),
            ],
        )
        result = await engine.execute(workflow, ExecutionContext())
        assert not result.success
        assert all(not sr.success for sr in result.step_results)

    async def test_partial_failure_in_parallel_group(self) -> None:
        """One failure in a parallel group does not affect independent steps."""
        call_count = 0

        async def selective_fail(request, ctx):
            nonlocal call_count
            call_count += 1
            if "fail" in request.url:
                return _mock_executor_response(error="boom")
            return _mock_executor_response()

        mock_executor = AsyncMock()
        mock_executor.execute_with_history = AsyncMock(side_effect=selective_fail)
        mock_hooks = AsyncMock()
        mock_hooks.run_pre_request = AsyncMock(side_effect=lambda ctx: ctx)
        mock_hooks.run_post_response = AsyncMock(side_effect=lambda ctx: ctx)
        engine = ParallelWorkflowEngine(request_executor=mock_executor, hook_runner=mock_hooks)

        workflow = WorkflowDef(
            id="wf1", name="Test",
            steps=[
                _make_request_step("a", url="https://ok.com"),
                _make_request_step("b", url="https://fail.com"),
            ],
        )
        result = await engine.execute(workflow, ExecutionContext())
        a_result = next(sr for sr in result.step_results if sr.step_id == "a")
        b_result = next(sr for sr in result.step_results if sr.step_id == "b")
        assert a_result.success
        assert not b_result.success
        assert not result.success


class TestParallelWorkflowEvents:
    """Tests for event publishing in parallel workflow engine."""

    async def test_publishes_started_and_completed(self) -> None:
        """workflow.started and workflow.completed events are published."""
        bus = SimpleEventBus()
        events: list[Event] = []
        bus.subscribe("*", lambda e: events.append(e))

        engine = _make_engine()
        engine._event_bus = bus
        workflow = WorkflowDef(id="wf1", name="Test", steps=[_make_request_step("s1")])
        await engine.execute(workflow, ExecutionContext())

        names = [e.name for e in events]
        assert "workflow.started" in names
        assert "workflow.completed" in names

    async def test_publishes_step_failed_for_failure(self) -> None:
        """workflow.step_failed is published when a step fails."""
        bus = SimpleEventBus()
        events: list[Event] = []
        bus.subscribe("*", lambda e: events.append(e))

        engine = _make_engine(error="err")
        engine._event_bus = bus
        workflow = WorkflowDef(id="wf1", name="Test", steps=[_make_request_step("s1")])
        await engine.execute(workflow, ExecutionContext())

        failed = [e for e in events if e.name == "workflow.step_failed"]
        assert len(failed) == 1


class TestParallelWorkflowDelay:
    """Tests for DELAY step type in parallel engine."""

    async def test_delay_step(self) -> None:
        """DELAY step sleeps and reports success."""
        engine = _make_engine()
        workflow = WorkflowDef(
            id="wf1", name="Test",
            steps=[_make_delay_step("d1", delay_ms=10)],
        )
        result = await engine.execute(workflow, ExecutionContext())
        assert result.success
        assert result.step_results[0].duration_ms >= 0
