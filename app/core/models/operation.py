"""Operation model for long-running background tasks.

Provides ExecutionOperation with a strict state machine, progress
tracking, and cancellation support.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class OperationStatus(StrEnum):
    """Terminal and non-terminal operation statuses."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"


class OperationType(StrEnum):
    """Types of operations the system can run."""

    WORKFLOW_RUN = "workflow_run"
    BATCH_RUN = "batch_run"
    MONITOR_START = "monitor_start"
    MONITOR_STOP = "monitor_stop"
    EXPORT = "export"
    IMPORT = "import"


# Valid state transitions — maps current status to set of reachable statuses
_TRANSITIONS: dict[OperationStatus, set[OperationStatus]] = {
    OperationStatus.QUEUED: {
        OperationStatus.RUNNING,
        OperationStatus.CANCELLED,
    },
    OperationStatus.RUNNING: {
        OperationStatus.SUCCEEDED,
        OperationStatus.FAILED,
        OperationStatus.CANCELLING,
    },
    OperationStatus.CANCELLING: {
        OperationStatus.CANCELLED,
        OperationStatus.FAILED,  # cancellation can fail
    },
    # Terminal states — no transitions out
    OperationStatus.SUCCEEDED: set(),
    OperationStatus.FAILED: set(),
    OperationStatus.CANCELLED: set(),
}

TERMINAL_STATUSES = {
    OperationStatus.SUCCEEDED,
    OperationStatus.FAILED,
    OperationStatus.CANCELLED,
}


class InvalidTransition(Exception):
    """Raised when an operation attempts an illegal state transition."""

    def __init__(self, current: OperationStatus, target: OperationStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"Cannot transition from {current.value!r} to {target.value!r}"
        )


@dataclass
class ExecutionOperation:
    """Represents a long-running background operation.

    State machine:
        QUEUED -> RUNNING -> SUCCEEDED | FAILED | CANCELLING -> CANCELLED
        QUEUED -> CANCELLED
        CANCELLING -> FAILED (if cancellation itself fails)
    """

    id: str
    project_id: str
    type: OperationType
    status: OperationStatus = OperationStatus.QUEUED
    progress: float = 0.0  # 0.0 to 1.0
    started_at: str | None = None
    finished_at: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(UTC).isoformat()

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    @property
    def is_cancellable(self) -> bool:
        return self.status in {OperationStatus.QUEUED, OperationStatus.RUNNING}

    def can_transition_to(self, target: OperationStatus) -> bool:
        """Check if a transition to *target* is valid without raising."""
        return target in _TRANSITIONS.get(self.status, set())

    def transition_to(self, target: OperationStatus) -> None:
        """Transition to *target*, raising InvalidTransition if illegal."""
        if not self.can_transition_to(target):
            raise InvalidTransition(self.status, target)
        self.status = target
        now = datetime.now(UTC).isoformat()
        if target == OperationStatus.RUNNING and self.started_at is None:
            self.started_at = now
        if target in TERMINAL_STATUSES:
            self.finished_at = now
            if target == OperationStatus.SUCCEEDED:
                self.progress = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the wire format (camelCase keys)."""
        return {
            "id": self.id,
            "projectId": self.project_id,
            "type": self.type.value,
            "status": self.status.value,
            "progress": self.progress,
            "createdAt": self.created_at,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "result": self.result,
            "error": self.error,
        }

    @classmethod
    def create(
        cls,
        project_id: str,
        operation_type: OperationType,
        *,
        operation_id: str | None = None,
    ) -> ExecutionOperation:
        """Factory for creating a new QUEUED operation."""
        return cls(
            id=operation_id or str(uuid.uuid4()),
            project_id=project_id,
            type=operation_type,
            status=OperationStatus.QUEUED,
        )
