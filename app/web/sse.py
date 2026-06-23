"""Server-Sent Events infrastructure.

Provides typed event schemas, an SSE serializer, a bounded per-project
replay buffer, and helpers for streaming events to clients.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

# ── Event types ──────────────────────────────────────────────────────────


class EventType(StrEnum):
    """Named SSE event types with explicit schemas."""

    # Operation lifecycle
    OPERATION_STARTED = "operation.started"
    OPERATION_PROGRESS = "operation.progress"
    OPERATION_COMPLETED = "operation.completed"
    OPERATION_FAILED = "operation.failed"
    OPERATION_CANCELLED = "operation.cancelled"

    # Stream management
    STREAM_RESET = "stream.reset"


# ── Event data schemas ───────────────────────────────────────────────────


@dataclass(frozen=True)
class OperationStartedData:
    """Data for operation.started events."""

    operation_id: str
    project_id: str
    operation_type: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "operationId": self.operation_id,
            "projectId": self.project_id,
            "operationType": self.operation_type,
        }


@dataclass(frozen=True)
class OperationProgressData:
    """Data for operation.progress events."""

    operation_id: str
    project_id: str
    progress: float
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "operationId": self.operation_id,
            "projectId": self.project_id,
            "progress": self.progress,
            "message": self.message,
        }


@dataclass(frozen=True)
class OperationCompletedData:
    """Data for operation.completed events."""

    operation_id: str
    project_id: str
    result: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operationId": self.operation_id,
            "projectId": self.project_id,
            "result": self.result,
        }


@dataclass(frozen=True)
class OperationFailedData:
    """Data for operation.failed events."""

    operation_id: str
    project_id: str
    error: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "operationId": self.operation_id,
            "projectId": self.project_id,
            "error": self.error,
        }


@dataclass(frozen=True)
class OperationCancelledData:
    """Data for operation.cancelled events."""

    operation_id: str
    project_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "operationId": self.operation_id,
            "projectId": self.project_id,
        }


@dataclass(frozen=True)
class StreamResetData:
    """Data for stream.reset events."""

    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"reason": self.reason}


# Union type for all event data
EventDataType = (
    OperationStartedData
    | OperationProgressData
    | OperationCompletedData
    | OperationFailedData
    | OperationCancelledData
    | StreamResetData
)


# ── Event envelope ───────────────────────────────────────────────────────


@dataclass
class StreamEvent:
    """An event envelope for SSE streaming.

    Every event has a unique ID, sequence number, and typed data.
    """

    id: str
    project_id: str
    operation_id: str | None
    event: EventType
    sequence: int
    occurred_at: str
    data: EventDataType

    def to_sse(self) -> str:
        """Format as an SSE text block.

        Returns:
            Formatted SSE string with id, event, and data fields.
        """
        data_dict = self.data.to_dict()
        # Remove None values for cleaner output
        data_dict = {k: v for k, v in data_dict.items() if v is not None}
        lines = [
            f"id: {self.id}",
            f"event: {self.event.value}",
            f"data: {json.dumps(data_dict, separators=(',', ':'))}",
            "",  # Empty line terminates the event
        ]
        return "\n".join(lines)

    @classmethod
    def create(
        cls,
        project_id: str,
        event_type: EventType,
        data: EventDataType,
        *,
        operation_id: str | None = None,
        sequence: int = 0,
    ) -> StreamEvent:
        """Factory for creating a new StreamEvent."""
        return cls(
            id=str(uuid.uuid4()),
            project_id=project_id,
            operation_id=operation_id,
            event=event_type,
            sequence=sequence,
            occurred_at=datetime.now(UTC).isoformat(),
            data=data,
        )


# ── Replay buffer ───────────────────────────────────────────────────────


class ReplayBuffer:
    """Bounded per-project replay buffer for SSE events.

    Stores recent events so clients can replay missed events after
    reconnection using Last-Event-ID.
    """

    def __init__(self, max_size: int = 1000) -> None:
        self._buffers: dict[str, deque[StreamEvent]] = defaultdict(
            lambda: deque(maxlen=max_size)
        )
        self._max_size = max_size
        self._sequence_counters: dict[str, int] = defaultdict(int)

    def add(self, event: StreamEvent) -> None:
        """Add an event to the buffer."""
        self._buffers[event.project_id].append(event)
        self._sequence_counters[event.project_id] = event.sequence

    def next_sequence(self, project_id: str) -> int:
        """Get the next sequence number for a project."""
        self._sequence_counters[project_id] += 1
        return self._sequence_counters[project_id]

    def get_events_since(
        self, project_id: str, last_event_id: str | None
    ) -> list[StreamEvent]:
        """Get events since a given event ID for replay.

        If last_event_id is None, returns all buffered events.
        If last_event_id is not found (evicted or never existed), returns
        an empty list to signal that a stream.reset is needed.
        """
        buf = self._buffers.get(project_id)
        if not buf:
            return []

        if last_event_id is None:
            return list(buf)

        # Find the position of last_event_id
        found_index = -1
        for i, event in enumerate(buf):
            if event.id == last_event_id:
                found_index = i
                break

        if found_index == -1:
            # Event not found — either never existed or was evicted
            # Return empty to signal stream.reset
            return []

        # Return events after the found one
        return list(buf)[found_index + 1 :]

    def clear(self, project_id: str | None = None) -> None:
        """Clear buffer for a project or all projects."""
        if project_id:
            self._buffers.pop(project_id, None)
            self._sequence_counters.pop(project_id, None)
        else:
            self._buffers.clear()
            self._sequence_counters.clear()

    def size(self, project_id: str) -> int:
        """Get buffer size for a project."""
        return len(self._buffers.get(project_id, []))


# ── SSE Manager ──────────────────────────────────────────────────────────


class SSEManager:
    """Manages SSE connections and event distribution.

    Coordinates event publishing, replay buffers, and client
    connections with heartbeat support.
    """

    HEARTBEAT_INTERVAL = 15  # seconds

    def __init__(self, replay_buffer: ReplayBuffer | None = None) -> None:
        self._replay_buffer = replay_buffer or ReplayBuffer()
        self._subscribers: dict[str, list[asyncio.Queue[StreamEvent | None]]] = (
            defaultdict(list)
        )
        self._heartbeat_tasks: dict[str, asyncio.Task] = {}

    @property
    def replay_buffer(self) -> ReplayBuffer:
        return self._replay_buffer

    def subscribe(self, project_id: str) -> asyncio.Queue[StreamEvent | None]:
        """Subscribe to events for a project. Returns a queue."""
        queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue()
        self._subscribers[project_id].append(queue)
        return queue

    def unsubscribe(
        self,
        project_id: str,
        queue: asyncio.Queue[StreamEvent | None],
    ) -> None:
        """Unsubscribe a queue from a project's events."""
        subs = self._subscribers.get(project_id, [])
        if queue in subs:
            subs.remove(queue)

    async def publish(self, event: StreamEvent) -> None:
        """Publish an event to all subscribers and add to replay buffer."""
        self._replay_buffer.add(event)
        queues = self._subscribers.get(event.project_id, [])
        for queue in queues:
            await queue.put(event)

    def get_replay_events(
        self, project_id: str, last_event_id: str | None
    ) -> list[StreamEvent]:
        """Get events for replay after reconnection."""
        return self._replay_buffer.get_events_since(
            project_id, last_event_id
        )

    async def start_heartbeat(
        self,
        project_id: str,
        queue: asyncio.Queue[StreamEvent | None],
    ) -> None:
        """Start sending heartbeat comments to a client queue."""
        key = f"{project_id}:{id(queue)}"

        async def _heartbeat_loop() -> None:
            while True:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                try:
                    await queue.put(None)
                except Exception:
                    break

        self._heartbeat_tasks[key] = asyncio.create_task(
            _heartbeat_loop()
        )

    async def stop_heartbeat(
        self,
        project_id: str,
        queue: asyncio.Queue[StreamEvent | None],
    ) -> None:
        """Stop heartbeat for a client queue."""
        key = f"{project_id}:{id(queue)}"
        task = self._heartbeat_tasks.pop(key, None)
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def shutdown(self) -> None:
        """Shutdown all heartbeat tasks."""
        for task in self._heartbeat_tasks.values():
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._heartbeat_tasks.clear()
