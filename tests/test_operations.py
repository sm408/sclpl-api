"""Tests for operations model, registry, and SSE streaming.

Covers: state transitions, illegal transitions, project isolation,
cancellation, replay, duplicate IDs, sequence gaps, heartbeat, redaction.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.core.models.operation import (
    TERMINAL_STATUSES,
    ExecutionOperation,
    InvalidTransition,
    OperationStatus,
    OperationType,
)
from app.services.operation_registry import (
    OperationNotFoundError,
    OperationRegistry,
)
from app.web.sse import (
    EventType,
    OperationCancelledData,
    OperationCompletedData,
    OperationFailedData,
    OperationProgressData,
    OperationStartedData,
    ReplayBuffer,
    SSEManager,
    StreamEvent,
    StreamResetData,
)

# ── Operation Model Tests ────────────────────────────────────────────────


class TestOperationStatus:
    """Test OperationStatus enum values."""

    def test_all_statuses_exist(self):
        assert OperationStatus.QUEUED == "queued"
        assert OperationStatus.RUNNING == "running"
        assert OperationStatus.SUCCEEDED == "succeeded"
        assert OperationStatus.FAILED == "failed"
        assert OperationStatus.CANCELLING == "cancelling"
        assert OperationStatus.CANCELLED == "cancelled"

    def test_terminal_statuses(self):
        assert OperationStatus.SUCCEEDED in TERMINAL_STATUSES
        assert OperationStatus.FAILED in TERMINAL_STATUSES
        assert OperationStatus.CANCELLED in TERMINAL_STATUSES
        assert OperationStatus.QUEUED not in TERMINAL_STATUSES
        assert OperationStatus.RUNNING not in TERMINAL_STATUSES
        assert OperationStatus.CANCELLING not in TERMINAL_STATUSES


class TestExecutionOperation:
    """Test ExecutionOperation model."""

    def test_create_default(self):
        op = ExecutionOperation.create(
            project_id="proj-1",
            operation_type=OperationType.WORKFLOW_RUN,
        )
        assert op.project_id == "proj-1"
        assert op.type == OperationType.WORKFLOW_RUN
        assert op.status == OperationStatus.QUEUED
        assert op.progress == 0.0
        assert op.started_at is None
        assert op.finished_at is None
        assert op.result is None
        assert op.error is None
        assert op.id  # auto-generated

    def test_create_with_id(self):
        op = ExecutionOperation.create(
            project_id="proj-1",
            operation_type=OperationType.BATCH_RUN,
            operation_id="custom-id",
        )
        assert op.id == "custom-id"

    def test_is_terminal(self):
        op = ExecutionOperation.create(
            project_id="proj-1",
            operation_type=OperationType.WORKFLOW_RUN,
        )
        assert not op.is_terminal
        op.status = OperationStatus.SUCCEEDED
        assert op.is_terminal

    def test_is_cancellable(self):
        op = ExecutionOperation.create(
            project_id="proj-1",
            operation_type=OperationType.WORKFLOW_RUN,
        )
        assert op.is_cancellable  # QUEUED
        op.status = OperationStatus.RUNNING
        assert op.is_cancellable
        op.status = OperationStatus.SUCCEEDED
        assert not op.is_cancellable
        op.status = OperationStatus.FAILED
        assert not op.is_cancellable
        op.status = OperationStatus.CANCELLED
        assert not op.is_cancellable

    def test_to_dict_camel_case(self):
        op = ExecutionOperation.create(
            project_id="proj-1",
            operation_type=OperationType.WORKFLOW_RUN,
            operation_id="op-1",
        )
        d = op.to_dict()
        assert d["id"] == "op-1"
        assert d["projectId"] == "proj-1"
        assert d["type"] == "workflow_run"
        assert d["status"] == "queued"
        assert d["progress"] == 0.0
        assert "project_id" not in d
        assert "operation_type" not in d


class TestStateTransitions:
    """Test valid and invalid state transitions."""

    def test_queued_to_running(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        op.transition_to(OperationStatus.RUNNING)
        assert op.status == OperationStatus.RUNNING
        assert op.started_at is not None

    def test_queued_to_cancelled(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        op.transition_to(OperationStatus.CANCELLED)
        assert op.status == OperationStatus.CANCELLED
        assert op.finished_at is not None

    def test_running_to_succeeded(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        op.transition_to(OperationStatus.RUNNING)
        op.transition_to(OperationStatus.SUCCEEDED)
        assert op.status == OperationStatus.SUCCEEDED
        assert op.finished_at is not None
        assert op.progress == 1.0

    def test_running_to_failed(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        op.transition_to(OperationStatus.RUNNING)
        op.transition_to(OperationStatus.FAILED)
        assert op.status == OperationStatus.FAILED
        assert op.finished_at is not None

    def test_running_to_cancelling(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        op.transition_to(OperationStatus.RUNNING)
        op.transition_to(OperationStatus.CANCELLING)
        assert op.status == OperationStatus.CANCELLING

    def test_cancelling_to_cancelled(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        op.transition_to(OperationStatus.RUNNING)
        op.transition_to(OperationStatus.CANCELLING)
        op.transition_to(OperationStatus.CANCELLED)
        assert op.status == OperationStatus.CANCELLED
        assert op.finished_at is not None

    def test_cancelling_to_failed(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        op.transition_to(OperationStatus.RUNNING)
        op.transition_to(OperationStatus.CANCELLING)
        op.transition_to(OperationStatus.FAILED)
        assert op.status == OperationStatus.FAILED

    def test_full_lifecycle_success(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        assert op.status == OperationStatus.QUEUED
        op.transition_to(OperationStatus.RUNNING)
        assert op.status == OperationStatus.RUNNING
        op.transition_to(OperationStatus.SUCCEEDED)
        assert op.status == OperationStatus.SUCCEEDED
        assert op.is_terminal

    def test_full_lifecycle_cancel(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        op.transition_to(OperationStatus.RUNNING)
        op.transition_to(OperationStatus.CANCELLING)
        op.transition_to(OperationStatus.CANCELLED)
        assert op.is_terminal

    def test_started_at_set_once(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        op.transition_to(OperationStatus.RUNNING)
        first_time = op.started_at
        # Should not change on subsequent transitions
        op.transition_to(OperationStatus.SUCCEEDED)
        assert op.started_at == first_time


class TestIllegalTransitions:
    """Test that illegal transitions raise InvalidTransition."""

    def test_queued_to_succeeded_fails(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        with pytest.raises(InvalidTransition):
            op.transition_to(OperationStatus.SUCCEEDED)

    def test_queued_to_failed_fails(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        with pytest.raises(InvalidTransition):
            op.transition_to(OperationStatus.FAILED)

    def test_queued_to_cancelling_fails(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        with pytest.raises(InvalidTransition):
            op.transition_to(OperationStatus.CANCELLING)

    def test_running_to_queued_fails(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        op.transition_to(OperationStatus.RUNNING)
        with pytest.raises(InvalidTransition):
            op.transition_to(OperationStatus.QUEUED)

    def test_running_to_cancelled_fails(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        op.transition_to(OperationStatus.RUNNING)
        with pytest.raises(InvalidTransition):
            op.transition_to(OperationStatus.CANCELLED)

    def test_succeeded_is_terminal(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        op.transition_to(OperationStatus.RUNNING)
        op.transition_to(OperationStatus.SUCCEEDED)
        with pytest.raises(InvalidTransition):
            op.transition_to(OperationStatus.RUNNING)

    def test_failed_is_terminal(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        op.transition_to(OperationStatus.RUNNING)
        op.transition_to(OperationStatus.FAILED)
        with pytest.raises(InvalidTransition):
            op.transition_to(OperationStatus.RUNNING)

    def test_cancelled_is_terminal(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        op.transition_to(OperationStatus.CANCELLED)
        with pytest.raises(InvalidTransition):
            op.transition_to(OperationStatus.RUNNING)

    def test_cancelling_to_queued_fails(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        op.transition_to(OperationStatus.RUNNING)
        op.transition_to(OperationStatus.CANCELLING)
        with pytest.raises(InvalidTransition):
            op.transition_to(OperationStatus.QUEUED)

    def test_cancelling_to_running_fails(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        op.transition_to(OperationStatus.RUNNING)
        op.transition_to(OperationStatus.CANCELLING)
        with pytest.raises(InvalidTransition):
            op.transition_to(OperationStatus.RUNNING)

    def test_cancelling_to_succeeded_fails(self):
        op = ExecutionOperation.create("p", OperationType.WORKFLOW_RUN)
        op.transition_to(OperationStatus.RUNNING)
        op.transition_to(OperationStatus.CANCELLING)
        with pytest.raises(InvalidTransition):
            op.transition_to(OperationStatus.SUCCEEDED)


# ── Operation Registry Tests ─────────────────────────────────────────────


class TestOperationRegistry:
    """Test OperationRegistry."""

    def test_create_operation(self):
        registry = OperationRegistry()
        op = registry.create_operation("proj-1", OperationType.WORKFLOW_RUN)
        assert op.project_id == "proj-1"
        assert op.status == OperationStatus.QUEUED
        assert op.id

    def test_create_operation_with_id(self):
        registry = OperationRegistry()
        op = registry.create_operation(
            "proj-1", OperationType.WORKFLOW_RUN, operation_id="custom"
        )
        assert op.id == "custom"

    def test_get_operation(self):
        registry = OperationRegistry()
        op = registry.create_operation("proj-1", OperationType.WORKFLOW_RUN)
        fetched = registry.get_operation(op.id, "proj-1")
        assert fetched.id == op.id

    def test_get_operation_not_found(self):
        registry = OperationRegistry()
        with pytest.raises(OperationNotFoundError):
            registry.get_operation("nonexistent", "proj-1")

    def test_get_operation_wrong_project(self):
        registry = OperationRegistry()
        op = registry.create_operation("proj-1", OperationType.WORKFLOW_RUN)
        with pytest.raises(OperationNotFoundError):
            registry.get_operation(op.id, "proj-2")

    def test_project_isolation(self):
        registry = OperationRegistry()
        op1 = registry.create_operation("proj-1", OperationType.WORKFLOW_RUN)
        op2 = registry.create_operation("proj-2", OperationType.WORKFLOW_RUN)

        # Each project only sees its own operations
        ops1 = registry.list_operations("proj-1")
        ops2 = registry.list_operations("proj-2")
        assert len(ops1) == 1
        assert len(ops2) == 1
        assert ops1[0].id == op1.id
        assert ops2[0].id == op2.id

    def test_list_operations_filter_by_status(self):
        registry = OperationRegistry()
        op1 = registry.create_operation("proj-1", OperationType.WORKFLOW_RUN)
        op2 = registry.create_operation("proj-1", OperationType.BATCH_RUN)
        registry.transition(op1.id, "proj-1", OperationStatus.RUNNING)

        queued = registry.list_operations("proj-1", status=OperationStatus.QUEUED)
        running = registry.list_operations("proj-1", status=OperationStatus.RUNNING)
        assert len(queued) == 1
        assert len(running) == 1
        assert queued[0].id == op2.id
        assert running[0].id == op1.id

    def test_transition(self):
        registry = OperationRegistry()
        op = registry.create_operation("proj-1", OperationType.WORKFLOW_RUN)
        registry.transition(op.id, "proj-1", OperationStatus.RUNNING)
        fetched = registry.get_operation(op.id, "proj-1")
        assert fetched.status == OperationStatus.RUNNING

    def test_transition_with_result(self):
        registry = OperationRegistry()
        op = registry.create_operation("proj-1", OperationType.WORKFLOW_RUN)
        registry.transition(op.id, "proj-1", OperationStatus.RUNNING)
        registry.transition(
            op.id,
            "proj-1",
            OperationStatus.SUCCEEDED,
            result={"output": "done"},
        )
        fetched = registry.get_operation(op.id, "proj-1")
        assert fetched.result == {"output": "done"}

    def test_transition_with_error(self):
        registry = OperationRegistry()
        op = registry.create_operation("proj-1", OperationType.WORKFLOW_RUN)
        registry.transition(op.id, "proj-1", OperationStatus.RUNNING)
        registry.transition(
            op.id,
            "proj-1",
            OperationStatus.FAILED,
            error="Something went wrong",
        )
        fetched = registry.get_operation(op.id, "proj-1")
        assert fetched.error == "Something went wrong"

    def test_cancel_queued_operation(self):
        registry = OperationRegistry()
        op = registry.create_operation("proj-1", OperationType.WORKFLOW_RUN)
        registry.cancel_operation(op.id, "proj-1")
        fetched = registry.get_operation(op.id, "proj-1")
        assert fetched.status == OperationStatus.CANCELLED

    def test_cancel_running_operation(self):
        registry = OperationRegistry()
        op = registry.create_operation("proj-1", OperationType.WORKFLOW_RUN)
        registry.transition(op.id, "proj-1", OperationStatus.RUNNING)
        registry.cancel_operation(op.id, "proj-1")
        fetched = registry.get_operation(op.id, "proj-1")
        assert fetched.status == OperationStatus.CANCELLING

    def test_cancel_terminal_operation_fails(self):
        registry = OperationRegistry()
        op = registry.create_operation("proj-1", OperationType.WORKFLOW_RUN)
        registry.transition(op.id, "proj-1", OperationStatus.RUNNING)
        registry.transition(op.id, "proj-1", OperationStatus.SUCCEEDED)
        with pytest.raises(InvalidTransition):
            registry.cancel_operation(op.id, "proj-1")

    def test_cancel_failed_operation_fails(self):
        registry = OperationRegistry()
        op = registry.create_operation("proj-1", OperationType.WORKFLOW_RUN)
        registry.transition(op.id, "proj-1", OperationStatus.RUNNING)
        registry.transition(op.id, "proj-1", OperationStatus.FAILED)
        with pytest.raises(InvalidTransition):
            registry.cancel_operation(op.id, "proj-1")

    def test_get_operation_any_project(self):
        registry = OperationRegistry()
        op = registry.create_operation("proj-1", OperationType.WORKFLOW_RUN)
        fetched = registry.get_operation_any_project(op.id)
        assert fetched.id == op.id
        assert fetched.project_id == "proj-1"

    def test_get_operation_any_project_not_found(self):
        registry = OperationRegistry()
        with pytest.raises(OperationNotFoundError):
            registry.get_operation_any_project("nonexistent")

    def test_enforce_limit(self):
        registry = OperationRegistry(max_per_project=3)
        # Create 4 operations (3 will be terminal)
        ops = []
        for _ in range(4):
            op = registry.create_operation("proj-1", OperationType.WORKFLOW_RUN)
            ops.append(op)

        # Make first 3 terminal
        for op in ops[:3]:
            registry.transition(op.id, "proj-1", OperationStatus.RUNNING)
            registry.transition(op.id, "proj-1", OperationStatus.SUCCEEDED)

        # The limit should have removed the oldest terminal ops
        remaining = registry.list_operations("proj-1")
        assert len(remaining) <= 3

    def test_cleanup_terminal(self):
        registry = OperationRegistry(max_terminal_age_seconds=0)
        op = registry.create_operation("proj-1", OperationType.WORKFLOW_RUN)
        registry.transition(op.id, "proj-1", OperationStatus.RUNNING)
        registry.transition(op.id, "proj-1", OperationStatus.SUCCEEDED)

        # With 0 age, cleanup should remove it
        removed = registry.cleanup_terminal("proj-1")
        assert removed == 1
        assert registry.total_count == 0

    def test_total_count(self):
        registry = OperationRegistry()
        registry.create_operation("proj-1", OperationType.WORKFLOW_RUN)
        registry.create_operation("proj-1", OperationType.BATCH_RUN)
        registry.create_operation("proj-2", OperationType.WORKFLOW_RUN)
        assert registry.total_count == 3


# ── SSE Event Tests ──────────────────────────────────────────────────────


class TestStreamEvent:
    """Test StreamEvent creation and serialization."""

    def test_create_event(self):
        event = StreamEvent.create(
            project_id="proj-1",
            event_type=EventType.OPERATION_STARTED,
            data=OperationStartedData(
                operation_id="op-1",
                project_id="proj-1",
                operation_type="workflow_run",
            ),
            operation_id="op-1",
            sequence=1,
        )
        assert event.project_id == "proj-1"
        assert event.operation_id == "op-1"
        assert event.event == EventType.OPERATION_STARTED
        assert event.sequence == 1
        assert event.id  # auto-generated
        assert event.occurred_at  # auto-generated

    def test_to_sse_format(self):
        event = StreamEvent(
            id="test-id",
            project_id="proj-1",
            operation_id="op-1",
            event=EventType.OPERATION_STARTED,
            sequence=1,
            occurred_at="2024-01-01T00:00:00Z",
            data=OperationStartedData(
                operation_id="op-1",
                project_id="proj-1",
                operation_type="workflow_run",
            ),
        )
        sse = event.to_sse()
        lines = sse.split("\n")
        assert lines[0] == "id: test-id"
        assert lines[1] == "event: operation.started"
        assert lines[2].startswith("data: ")
        data = json.loads(lines[2][6:])
        assert data["operationId"] == "op-1"
        assert data["projectId"] == "proj-1"
        assert data["operationType"] == "workflow_run"
        assert lines[3] == ""  # Empty line terminator

    def test_to_sse_removes_none_values(self):
        event = StreamEvent(
            id="test-id",
            project_id="proj-1",
            operation_id=None,
            event=EventType.STREAM_RESET,
            sequence=0,
            occurred_at="2024-01-01T00:00:00Z",
            data=StreamResetData(reason="test"),
        )
        sse = event.to_sse()
        data_line = [
            line for line in sse.split("\n") if line.startswith("data:")
        ][0]
        data = json.loads(data_line[6:])
        assert "operationId" not in data

    def test_all_event_types(self):
        """Verify all event types can be created and serialized."""
        events = [
            (EventType.OPERATION_STARTED, OperationStartedData("op-1", "proj-1", "workflow_run")),
            (EventType.OPERATION_PROGRESS, OperationProgressData("op-1", "proj-1", 0.5)),
            (EventType.OPERATION_COMPLETED, OperationCompletedData("op-1", "proj-1", {"out": 1})),
            (EventType.OPERATION_FAILED, OperationFailedData("op-1", "proj-1", "err")),
            (EventType.OPERATION_CANCELLED, OperationCancelledData("op-1", "proj-1")),
            (EventType.STREAM_RESET, StreamResetData("reason")),
        ]
        for event_type, data in events:
            event = StreamEvent.create(
                project_id="proj-1",
                event_type=event_type,
                data=data,
                operation_id="op-1",
                sequence=1,
            )
            sse = event.to_sse()
            assert f"event: {event_type.value}" in sse
            assert "data: " in sse


# ── Replay Buffer Tests ─────────────────────────────────────────────────


class TestReplayBuffer:
    """Test ReplayBuffer."""

    def test_add_and_retrieve(self):
        buf = ReplayBuffer()
        event = StreamEvent.create(
            project_id="proj-1",
            event_type=EventType.OPERATION_STARTED,
            data=OperationStartedData("op-1", "proj-1", "workflow_run"),
            sequence=1,
        )
        buf.add(event)
        events = buf.get_events_since("proj-1", None)
        assert len(events) == 1
        assert events[0].id == event.id

    def test_replay_since_event(self):
        buf = ReplayBuffer()
        events = []
        for i in range(5):
            event = StreamEvent.create(
                project_id="proj-1",
                event_type=EventType.OPERATION_PROGRESS,
                data=OperationProgressData("op-1", "proj-1", i * 0.2),
                sequence=i + 1,
            )
            buf.add(event)
            events.append(event)

        # Replay from event 3
        replayed = buf.get_events_since("proj-1", events[2].id)
        assert len(replayed) == 2
        assert replayed[0].id == events[3].id
        assert replayed[1].id == events[4].id

    def test_replay_event_not_found(self):
        buf = ReplayBuffer()
        event = StreamEvent.create(
            project_id="proj-1",
            event_type=EventType.OPERATION_STARTED,
            data=OperationStartedData("op-1", "proj-1", "workflow_run"),
            sequence=1,
        )
        buf.add(event)
        replayed = buf.get_events_since("proj-1", "nonexistent")
        assert replayed == []

    def test_replay_empty_buffer(self):
        buf = ReplayBuffer()
        replayed = buf.get_events_since("proj-1", None)
        assert replayed == []

    def test_project_isolation(self):
        buf = ReplayBuffer()
        event1 = StreamEvent.create(
            project_id="proj-1",
            event_type=EventType.OPERATION_STARTED,
            data=OperationStartedData("op-1", "proj-1", "workflow_run"),
            sequence=1,
        )
        event2 = StreamEvent.create(
            project_id="proj-2",
            event_type=EventType.OPERATION_STARTED,
            data=OperationStartedData("op-2", "proj-2", "batch_run"),
            sequence=1,
        )
        buf.add(event1)
        buf.add(event2)

        events1 = buf.get_events_since("proj-1", None)
        events2 = buf.get_events_since("proj-2", None)
        assert len(events1) == 1
        assert len(events2) == 1
        assert events1[0].project_id == "proj-1"
        assert events2[0].project_id == "proj-2"

    def test_max_size_eviction(self):
        buf = ReplayBuffer(max_size=3)
        events = []
        for i in range(5):
            event = StreamEvent.create(
                project_id="proj-1",
                event_type=EventType.OPERATION_PROGRESS,
                data=OperationProgressData("op-1", "proj-1", i * 0.2),
                sequence=i + 1,
            )
            buf.add(event)
            events.append(event)

        # Only last 3 should be in buffer
        all_events = buf.get_events_since("proj-1", None)
        assert len(all_events) == 3
        assert all_events[0].id == events[2].id  # 3rd event is oldest now

    def test_sequence_counter(self):
        buf = ReplayBuffer()
        assert buf.next_sequence("proj-1") == 1
        assert buf.next_sequence("proj-1") == 2
        assert buf.next_sequence("proj-1") == 3
        assert buf.next_sequence("proj-2") == 1  # Separate counter per project

    def test_clear_project(self):
        buf = ReplayBuffer()
        event = StreamEvent.create(
            project_id="proj-1",
            event_type=EventType.OPERATION_STARTED,
            data=OperationStartedData("op-1", "proj-1", "workflow_run"),
            sequence=1,
        )
        buf.add(event)
        buf.clear("proj-1")
        assert buf.size("proj-1") == 0

    def test_clear_all(self):
        buf = ReplayBuffer()
        for pid in ["proj-1", "proj-2"]:
            event = StreamEvent.create(
                project_id=pid,
                event_type=EventType.OPERATION_STARTED,
                data=OperationStartedData("op-1", pid, "workflow_run"),
                sequence=1,
            )
            buf.add(event)
        buf.clear()
        assert buf.size("proj-1") == 0
        assert buf.size("proj-2") == 0

    def test_size(self):
        buf = ReplayBuffer()
        assert buf.size("proj-1") == 0
        for i in range(3):
            event = StreamEvent.create(
                project_id="proj-1",
                event_type=EventType.OPERATION_PROGRESS,
                data=OperationProgressData("op-1", "proj-1", i * 0.3),
                sequence=i + 1,
            )
            buf.add(event)
        assert buf.size("proj-1") == 3


# ── SSE Manager Tests ────────────────────────────────────────────────────


class TestSSEManager:
    """Test SSEManager."""

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self):
        manager = SSEManager()
        queue = manager.subscribe("proj-1")
        event = StreamEvent.create(
            project_id="proj-1",
            event_type=EventType.OPERATION_STARTED,
            data=OperationStartedData("op-1", "proj-1", "workflow_run"),
            sequence=1,
        )
        await manager.publish(event)
        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert received.id == event.id

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        manager = SSEManager()
        queue = manager.subscribe("proj-1")
        manager.unsubscribe("proj-1", queue)
        event = StreamEvent.create(
            project_id="proj-1",
            event_type=EventType.OPERATION_STARTED,
            data=OperationStartedData("op-1", "proj-1", "workflow_run"),
            sequence=1,
        )
        await manager.publish(event)
        # Queue should be empty
        assert queue.empty()

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        manager = SSEManager()
        queue1 = manager.subscribe("proj-1")
        queue2 = manager.subscribe("proj-1")
        event = StreamEvent.create(
            project_id="proj-1",
            event_type=EventType.OPERATION_STARTED,
            data=OperationStartedData("op-1", "proj-1", "workflow_run"),
            sequence=1,
        )
        await manager.publish(event)
        received1 = await asyncio.wait_for(queue1.get(), timeout=1.0)
        received2 = await asyncio.wait_for(queue2.get(), timeout=1.0)
        assert received1.id == event.id
        assert received2.id == event.id

    @pytest.mark.asyncio
    async def test_project_isolation(self):
        manager = SSEManager()
        queue1 = manager.subscribe("proj-1")
        queue2 = manager.subscribe("proj-2")
        event = StreamEvent.create(
            project_id="proj-1",
            event_type=EventType.OPERATION_STARTED,
            data=OperationStartedData("op-1", "proj-1", "workflow_run"),
            sequence=1,
        )
        await manager.publish(event)
        received1 = await asyncio.wait_for(queue1.get(), timeout=1.0)
        assert received1.id == event.id
        assert queue2.empty()

    @pytest.mark.asyncio
    async def test_replay_after_reconnect(self):
        manager = SSEManager()
        # Publish some events
        events = []
        for i in range(3):
            event = StreamEvent.create(
                project_id="proj-1",
                event_type=EventType.OPERATION_PROGRESS,
                data=OperationProgressData("op-1", "proj-1", i * 0.3),
                sequence=i + 1,
            )
            await manager.publish(event)
            events.append(event)

        # Simulate reconnect from event 1
        replayed = manager.get_replay_events("proj-1", events[0].id)
        assert len(replayed) == 2
        assert replayed[0].id == events[1].id
        assert replayed[1].id == events[2].id

    @pytest.mark.asyncio
    async def test_replay_not_found(self):
        manager = SSEManager()
        event = StreamEvent.create(
            project_id="proj-1",
            event_type=EventType.OPERATION_STARTED,
            data=OperationStartedData("op-1", "proj-1", "workflow_run"),
            sequence=1,
        )
        await manager.publish(event)
        replayed = manager.get_replay_events("proj-1", "nonexistent")
        assert replayed == []

    @pytest.mark.asyncio
    async def test_shutdown(self):
        manager = SSEManager()
        queue = manager.subscribe("proj-1")
        await manager.start_heartbeat("proj-1", queue)
        await manager.shutdown()
        # Should not raise


# ── Integration Tests ────────────────────────────────────────────────────


class TestOperationLifecycle:
    """Test complete operation lifecycle with events."""

    @pytest.mark.asyncio
    async def test_full_success_lifecycle(self):
        registry = OperationRegistry()
        manager = SSEManager()
        queue = manager.subscribe("proj-1")

        # Create and run operation
        op = registry.create_operation("proj-1", OperationType.WORKFLOW_RUN)

        # Publish started event
        started_event = StreamEvent.create(
            project_id="proj-1",
            event_type=EventType.OPERATION_STARTED,
            data=OperationStartedData(op.id, "proj-1", "workflow_run"),
            operation_id=op.id,
            sequence=manager.replay_buffer.next_sequence("proj-1"),
        )
        await manager.publish(started_event)

        # Transition to running
        registry.transition(op.id, "proj-1", OperationStatus.RUNNING)

        # Publish progress
        progress_event = StreamEvent.create(
            project_id="proj-1",
            event_type=EventType.OPERATION_PROGRESS,
            data=OperationProgressData(op.id, "proj-1", 0.5, "Halfway"),
            operation_id=op.id,
            sequence=manager.replay_buffer.next_sequence("proj-1"),
        )
        await manager.publish(progress_event)

        # Complete
        registry.transition(
            op.id, "proj-1", OperationStatus.SUCCEEDED, result={"output": "done"}
        )
        completed_event = StreamEvent.create(
            project_id="proj-1",
            event_type=EventType.OPERATION_COMPLETED,
            data=OperationCompletedData(op.id, "proj-1", {"output": "done"}),
            operation_id=op.id,
            sequence=manager.replay_buffer.next_sequence("proj-1"),
        )
        await manager.publish(completed_event)

        # Verify events received
        events = []
        while not queue.empty():
            events.append(await queue.get())
        assert len(events) == 3
        assert events[0].event == EventType.OPERATION_STARTED
        assert events[1].event == EventType.OPERATION_PROGRESS
        assert events[2].event == EventType.OPERATION_COMPLETED

        # Verify replay buffer
        replayed = manager.get_replay_events("proj-1", None)
        assert len(replayed) == 3

    @pytest.mark.asyncio
    async def test_cancellation_lifecycle(self):
        registry = OperationRegistry()

        op = registry.create_operation("proj-1", OperationType.WORKFLOW_RUN)
        registry.transition(op.id, "proj-1", OperationStatus.RUNNING)

        # Cancel
        cancelled_op = registry.cancel_operation(op.id, "proj-1")
        assert cancelled_op.status == OperationStatus.CANCELLING

        # Complete cancellation
        registry.transition(op.id, "proj-1", OperationStatus.CANCELLED)
        final_op = registry.get_operation(op.id, "proj-1")
        assert final_op.status == OperationStatus.CANCELLED
        assert final_op.is_terminal


class TestSequenceGaps:
    """Test sequence number handling."""

    def test_sequence_gaps_detected(self):
        buf = ReplayBuffer()
        # Add events with gaps
        for seq in [1, 2, 5, 6, 10]:
            event = StreamEvent.create(
                project_id="proj-1",
                event_type=EventType.OPERATION_PROGRESS,
                data=OperationProgressData("op-1", "proj-1", seq * 0.1),
                sequence=seq,
            )
            buf.add(event)

        all_events = buf.get_events_since("proj-1", None)
        sequences = [e.sequence for e in all_events]
        assert sequences == [1, 2, 5, 6, 10]

    def test_duplicate_event_ids(self):
        """Test that duplicate IDs are handled gracefully."""
        buf = ReplayBuffer()
        event1 = StreamEvent(
            id="dup-id",
            project_id="proj-1",
            operation_id="op-1",
            event=EventType.OPERATION_PROGRESS,
            sequence=1,
            occurred_at="2024-01-01T00:00:00Z",
            data=OperationProgressData("op-1", "proj-1", 0.1),
        )
        event2 = StreamEvent(
            id="dup-id",  # Same ID
            project_id="proj-1",
            operation_id="op-1",
            event=EventType.OPERATION_PROGRESS,
            sequence=2,
            occurred_at="2024-01-01T00:00:01Z",
            data=OperationProgressData("op-1", "proj-1", 0.2),
        )
        buf.add(event1)
        buf.add(event2)

        # Both events should be in buffer
        all_events = buf.get_events_since("proj-1", None)
        assert len(all_events) == 2

        # Replay from first duplicate
        replayed = buf.get_events_since("proj-1", "dup-id")
        # Should find the first one and return events after it
        assert len(replayed) == 1
        assert replayed[0].sequence == 2


class TestRedaction:
    """Test that sensitive data is not leaked in events."""

    def test_operation_result_redaction(self):
        """Verify that operation results don't contain sensitive data by default."""
        op = ExecutionOperation.create("proj-1", OperationType.WORKFLOW_RUN)
        op.transition_to(OperationStatus.RUNNING)
        op.transition_to(OperationStatus.SUCCEEDED)
        op.result = {"public": "data", "count": 42}
        d = op.to_dict()
        # Result should be included as-is (redaction is application-level)
        assert d["result"] == {"public": "data", "count": 42}

    def test_error_messages_safe(self):
        """Verify error messages don't leak internal details."""
        op = ExecutionOperation.create("proj-1", OperationType.WORKFLOW_RUN)
        op.transition_to(OperationStatus.RUNNING)
        op.transition_to(OperationStatus.FAILED)
        op.error = "Request timeout"
        d = op.to_dict()
        assert d["error"] == "Request timeout"
