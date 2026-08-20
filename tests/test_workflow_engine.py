from __future__ import annotations

from unittest.mock import AsyncMock

from app.core.contracts.event_bus import Event
from app.core.contracts.request_executor import ResponseResult
from app.core.engine.event_bus import SimpleEventBus
from app.core.engine.workflow import WorkflowEngine
from app.core.models.context import ExecutionContext
from app.core.models.history import HistoryEntry, RunStatus
from app.core.models.workflow import (
    RetryConfig,
    RetryStrategy,
    StepType,
    WorkflowDef,
    WorkflowStep,
)


def _make_request_step(step_id: str, url: str = "https://example.com", **kwargs) -> WorkflowStep:
    return WorkflowStep(
        id=step_id,
        name=step_id,
        step_type=StepType.REQUEST,
        config={
            "inline_request": {
                "method": "GET",
                "url": url,
                "headers": {},
            }
        },
        **kwargs,
    )


def _make_function_step(step_id: str, function_name: str = "test_fn", **kwargs) -> WorkflowStep:
    return WorkflowStep(
        id=step_id,
        name=step_id,
        step_type=StepType.FUNCTION,
        config={"function_name": function_name},
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


def _mock_executor_response(status_code: int = 200, body: str = '{"ok": true}', error: str | None = None):
    """Create a mock execute_with_history returning a fixed ResponseResult."""
    result = ResponseResult(
        status_code=status_code,
        headers={"content-type": "application/json"},
        body=body,
        duration_ms=10,
        error=error,
    )
    entry = HistoryEntry(
        id="h1",
        request_id="r1",
        request_name="test",
        method="GET",
        url="https://example.com",
        status=RunStatus.SUCCESS if not error else RunStatus.ERROR,
        status_code=status_code,
        response_body=body,
        duration_ms=10,
        error_message=error,
    )
    return result, entry


def _make_engine_with_mock_executor(status_code=200, body='{"ok": true}', error=None):
    """Build a WorkflowEngine with a mocked HttpRequestExecutor."""
    mock_executor = AsyncMock()
    mock_executor.execute_with_history = AsyncMock(
        return_value=_mock_executor_response(status_code, body, error)
    )
    mock_hooks = AsyncMock()
    mock_hooks.run_pre_request = AsyncMock(side_effect=lambda ctx: ctx)
    mock_hooks.run_post_response = AsyncMock(side_effect=lambda ctx: ctx)
    return WorkflowEngine(
        request_executor=mock_executor,
        hook_runner=mock_hooks,
    )


class TestWorkflowEngineExecute:
    """Tests for WorkflowEngine.execute() with various workflow configurations."""

    async def test_execute_simple_request_step(self) -> None:
        """A single request step executes successfully and returns status code in output."""
        engine = _make_engine_with_mock_executor()
        workflow = WorkflowDef(
            id="wf1", name="Test", steps=[_make_request_step("s1")],
        )
        result = await engine.execute(workflow, ExecutionContext())
        assert result.success
        assert len(result.step_results) == 1
        assert result.step_results[0].success
        assert result.step_results[0].output["status_code"] == 200

    async def test_execute_sequential_steps_with_deps(self) -> None:
        """Steps with dependencies execute in topological order."""
        engine = _make_engine_with_mock_executor()
        workflow = WorkflowDef(
            id="wf1", name="Test",
            steps=[
                _make_request_step("a"),
                _make_request_step("b", depends_on=["a"]),
                _make_request_step("c", depends_on=["b"]),
            ],
        )
        result = await engine.execute(workflow, ExecutionContext())
        assert result.success
        ids = [sr.step_id for sr in result.step_results]
        assert ids == ["a", "b", "c"]

    async def test_execute_step_failure(self) -> None:
        """A step that returns an error causes the workflow to report failure."""
        engine = _make_engine_with_mock_executor(error="Connection refused")
        workflow = WorkflowDef(
            id="wf1", name="Test", steps=[_make_request_step("s1")],
        )
        result = await engine.execute(workflow, ExecutionContext())
        assert not result.success
        assert result.step_results[0].error == "Connection refused"

    async def test_execute_delay_step(self) -> None:
        """A DELAY step sleeps and succeeds."""
        engine = _make_engine_with_mock_executor()
        workflow = WorkflowDef(
            id="wf1", name="Test", steps=[_make_delay_step("d1", delay_ms=10)],
        )
        result = await engine.execute(workflow, ExecutionContext())
        assert result.success
        assert result.step_results[0].duration_ms >= 0

    async def test_execute_with_variable_resolution(self) -> None:
        """Variables in inline request URLs are resolved before execution."""
        mock_executor = AsyncMock()
        mock_executor.execute_with_history = AsyncMock(
            return_value=_mock_executor_response(200, '{"ok": true}')
        )
        mock_hooks = AsyncMock()
        mock_hooks.run_pre_request = AsyncMock(side_effect=lambda ctx: ctx)
        mock_hooks.run_post_response = AsyncMock(side_effect=lambda ctx: ctx)
        engine = WorkflowEngine(
            request_executor=mock_executor,
            hook_runner=mock_hooks,
        )
        step = WorkflowStep(
            id="s1", name="s1", step_type=StepType.REQUEST,
            config={"inline_request": {"method": "GET", "url": "https://{{host}}/api", "headers": {}}},
        )
        workflow = WorkflowDef(id="wf1", name="Test", steps=[step])
        ctx = ExecutionContext(variables={"host": "api.example.com"})
        await engine.execute(workflow, ctx)
        called_request = mock_executor.execute_with_history.call_args[0][0]
        assert called_request.url == "https://api.example.com/api"

    async def test_execute_output_variable_stored(self) -> None:
        """When a step has output_variable, the result is stored in workflow_variables."""
        engine = _make_engine_with_mock_executor(body='{"id": 42}')
        step = _make_request_step("s1")
        step.output_variable = "created_id"
        workflow = WorkflowDef(id="wf1", name="Test", steps=[step])
        ctx = ExecutionContext()
        result = await engine.execute(workflow, ctx)
        assert ctx.workflow_variables["created_id"] != ""

    async def test_execute_skip_condition_false(self) -> None:
        """A step whose condition evaluates to False is skipped."""
        engine = _make_engine_with_mock_executor()
        step = _make_request_step("s1")
        step.condition = 'False'
        workflow = WorkflowDef(id="wf1", name="Test", steps=[step])
        result = await engine.execute(workflow, ExecutionContext())
        assert result.success
        assert result.step_results[0].output == "skipped"

    async def test_execute_condition_true_runs(self) -> None:
        """A step whose condition evaluates to True runs normally."""
        engine = _make_engine_with_mock_executor()
        step = _make_request_step("s1")
        step.condition = 'True'
        workflow = WorkflowDef(id="wf1", name="Test", steps=[step])
        result = await engine.execute(workflow, ExecutionContext())
        assert result.success
        assert result.step_results[0].output != "skipped"


class TestWorkflowEngineRetry:
    """Tests for retry logic in WorkflowEngine."""

    async def test_retry_on_failure_eventually_succeeds(self) -> None:
        """A step that fails then succeeds on retry returns success."""
        call_count = 0

        async def side_effect(request, ctx):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_executor_response(error="timeout")
            return _mock_executor_response(200, '{"ok": true}')

        mock_executor = AsyncMock()
        mock_executor.execute_with_history = AsyncMock(side_effect=side_effect)
        mock_hooks = AsyncMock()
        mock_hooks.run_pre_request = AsyncMock(side_effect=lambda ctx: ctx)
        mock_hooks.run_post_response = AsyncMock(side_effect=lambda ctx: ctx)

        engine = WorkflowEngine(request_executor=mock_executor, hook_runner=mock_hooks)
        step = _make_request_step("s1")
        step.retry = RetryConfig(max_retries=2, strategy=RetryStrategy.FIXED, delay_ms=1)
        workflow = WorkflowDef(id="wf1", name="Test", steps=[step])
        result = await engine.execute(workflow, ExecutionContext())
        assert result.success
        assert call_count == 2

    async def test_retry_exhausted_still_fails(self) -> None:
        """When all retries fail, the step reports failure."""
        mock_executor = AsyncMock()
        mock_executor.execute_with_history = AsyncMock(
            return_value=_mock_executor_response(error="always fails")
        )
        mock_hooks = AsyncMock()
        mock_hooks.run_pre_request = AsyncMock(side_effect=lambda ctx: ctx)
        mock_hooks.run_post_response = AsyncMock(side_effect=lambda ctx: ctx)

        engine = WorkflowEngine(request_executor=mock_executor, hook_runner=mock_hooks)
        step = _make_request_step("s1")
        step.retry = RetryConfig(max_retries=2, strategy=RetryStrategy.FIXED, delay_ms=1)
        workflow = WorkflowDef(id="wf1", name="Test", steps=[step])
        result = await engine.execute(workflow, ExecutionContext())
        assert not result.success


class TestWorkflowEngineEvents:
    """Tests for event publishing during workflow execution."""

    async def test_publishes_started_and_completed_events(self) -> None:
        """Workflow execution publishes workflow.started and workflow.completed events."""
        bus = SimpleEventBus()
        events: list[Event] = []
        bus.subscribe("*", lambda e: events.append(e))

        engine = _make_engine_with_mock_executor()
        engine._event_bus = bus
        workflow = WorkflowDef(id="wf1", name="Test", steps=[_make_request_step("s1")])
        await engine.execute(workflow, ExecutionContext())

        event_names = [e.name for e in events]
        assert "workflow.started" in event_names
        assert "workflow.completed" in event_names

    async def test_publishes_step_failed_event(self) -> None:
        """A failing step publishes workflow.step_failed event."""
        bus = SimpleEventBus()
        events: list[Event] = []
        bus.subscribe("*", lambda e: events.append(e))

        engine = _make_engine_with_mock_executor(error="boom")
        engine._event_bus = bus
        workflow = WorkflowDef(id="wf1", name="Test", steps=[_make_request_step("s1")])
        await engine.execute(workflow, ExecutionContext())

        step_failed = [e for e in events if e.name == "workflow.step_failed"]
        assert len(step_failed) == 1
        assert step_failed[0].data["error"] == "boom"


class TestWorkflowEngineTopologicalSort:
    """Tests for the topological sort of steps."""

    async def test_topological_sort_preserves_order(self) -> None:
        """Steps are sorted so dependencies come before dependents."""
        engine = WorkflowEngine()
        steps = [
            _make_request_step("c", depends_on=["a", "b"]),
            _make_request_step("a"),
            _make_request_step("b", depends_on=["a"]),
        ]
        sorted_steps = engine._topological_sort(steps)
        ids = [s.id for s in sorted_steps]
        assert ids.index("a") < ids.index("b")
        assert ids.index("b") < ids.index("c")

    async def test_topological_sort_independent_steps(self) -> None:
        """Independent steps maintain their original order."""
        engine = WorkflowEngine()
        steps = [_make_request_step("x"), _make_request_step("y"), _make_request_step("z")]
        sorted_steps = engine._topological_sort(steps)
        ids = [s.id for s in sorted_steps]
        assert ids == ["x", "y", "z"]

    async def test_topological_sort_unknown_dep_ignored(self) -> None:
        """A dependency on a non-existent step does not crash."""
        engine = WorkflowEngine()
        steps = [_make_request_step("a", depends_on=["nonexistent"])]
        sorted_steps = engine._topological_sort(steps)
        assert len(sorted_steps) == 1
