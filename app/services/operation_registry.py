"""In-memory operation registry with retention management.

Provides OperationRegistry which tracks ExecutionOperation instances,
enforces project isolation, and handles cleanup of terminal operations.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import UTC, datetime

from app.core.models.operation import (
    ExecutionOperation,
    InvalidTransition,
    OperationStatus,
    OperationType,
)

logger = logging.getLogger(__name__)

# Default retention settings
DEFAULT_MAX_OPERATIONS_PER_PROJECT = 100
DEFAULT_MAX_TERMINAL_AGE_SECONDS = 3600  # 1 hour


class OperationNotFoundError(Exception):
    """Raised when an operation ID is not found."""

    def __init__(self, operation_id: str) -> None:
        self.operation_id = operation_id
        super().__init__(f"Operation '{operation_id}' not found")


class OperationRegistryError(Exception):
    """Base for registry errors."""


class OperationRegistry:
    """Thread-safe in-memory operation registry.

    Operations are scoped by project_id. Each project has a bounded
    number of retained terminal operations.
    """

    def __init__(
        self,
        *,
        max_per_project: int = DEFAULT_MAX_OPERATIONS_PER_PROJECT,
        max_terminal_age_seconds: int = DEFAULT_MAX_TERMINAL_AGE_SECONDS,
    ) -> None:
        self._operations: dict[str, dict[str, ExecutionOperation]] = defaultdict(dict)
        self._max_per_project = max_per_project
        self._max_terminal_age = max_terminal_age_seconds
        self._lock = asyncio.Lock()

    # ── Internal (unlocked) implementations ──────────────────────────────

    def _create_operation_impl(
        self,
        project_id: str,
        operation_type: OperationType,
        *,
        operation_id: str | None = None,
    ) -> ExecutionOperation:
        """Create and register a new QUEUED operation (no lock)."""
        op = ExecutionOperation.create(
            project_id=project_id,
            operation_type=operation_type,
            operation_id=operation_id,
        )
        self._operations[project_id][op.id] = op
        self._enforce_limit(project_id)
        return op

    def _get_operation_impl(self, operation_id: str, project_id: str) -> ExecutionOperation:
        """Retrieve an operation by ID, scoped to a project (no lock)."""
        op = self._operations.get(project_id, {}).get(operation_id)
        if op is None:
            raise OperationNotFoundError(operation_id)
        return op

    def _get_operation_any_project_impl(self, operation_id: str) -> ExecutionOperation:
        """Retrieve an operation by ID across all projects (no lock)."""
        for project_ops in self._operations.values():
            if operation_id in project_ops:
                return project_ops[operation_id]
        raise OperationNotFoundError(operation_id)

    def _list_operations_impl(
        self,
        project_id: str,
        *,
        status: OperationStatus | None = None,
    ) -> list[ExecutionOperation]:
        """List all operations for a project (no lock)."""
        ops = list(self._operations.get(project_id, {}).values())
        if status is not None:
            ops = [op for op in ops if op.status == status]
        return sorted(ops, key=lambda o: o.created_at, reverse=True)

    def _transition_impl(
        self,
        operation_id: str,
        project_id: str,
        target: OperationStatus,
        *,
        result: dict | None = None,
        error: str | None = None,
        progress: float | None = None,
    ) -> ExecutionOperation:
        """Transition an operation to a new status (no lock)."""
        op = self._get_operation_impl(operation_id, project_id)
        op.transition_to(target)
        if result is not None:
            op.result = result
        if error is not None:
            op.error = error
        if progress is not None:
            op.progress = progress
        # Enforce limit after terminal transitions
        if op.is_terminal:
            self._enforce_limit(project_id)
        return op

    def _cancel_operation_impl(
        self,
        operation_id: str,
        project_id: str,
    ) -> ExecutionOperation:
        """Request cancellation of an operation (no lock)."""
        op = self._get_operation_impl(operation_id, project_id)
        if op.status == OperationStatus.QUEUED:
            op.transition_to(OperationStatus.CANCELLED)
        elif op.status == OperationStatus.RUNNING:
            op.transition_to(OperationStatus.CANCELLING)
        elif op.status == OperationStatus.CANCELLING:
            # Already cancelling — idempotent, return as-is
            pass
        else:
            raise InvalidTransition(op.status, OperationStatus.CANCELLED)
        return op

    def _cleanup_terminal_impl(self, project_id: str | None = None) -> int:
        """Remove expired terminal operations (no lock)."""
        now = datetime.now(UTC)
        removed = 0
        project_ids = [project_id] if project_id else list(self._operations.keys())
        for pid in project_ids:
            ops = self._operations.get(pid, {})
            to_remove = []
            for op_id, op in ops.items():
                if op.is_terminal and op.finished_at:
                    finished = datetime.fromisoformat(op.finished_at)
                    age = (now - finished).total_seconds()
                    if age > self._max_terminal_age:
                        to_remove.append(op_id)
            for op_id in to_remove:
                del ops[op_id]
                removed += 1
        return removed

    # ── Public (locked) API ──────────────────────────────────────────────

    async def create_operation(
        self,
        project_id: str,
        operation_type: OperationType,
        *,
        operation_id: str | None = None,
    ) -> ExecutionOperation:
        """Create and register a new QUEUED operation."""
        async with self._lock:
            return self._create_operation_impl(
                project_id, operation_type, operation_id=operation_id
            )

    async def get_operation(self, operation_id: str, project_id: str) -> ExecutionOperation:
        """Retrieve an operation by ID, scoped to a project."""
        async with self._lock:
            return self._get_operation_impl(operation_id, project_id)

    async def get_operation_any_project(self, operation_id: str) -> ExecutionOperation:
        """Retrieve an operation by ID across all projects."""
        async with self._lock:
            return self._get_operation_any_project_impl(operation_id)

    async def list_operations(
        self,
        project_id: str,
        *,
        status: OperationStatus | None = None,
    ) -> list[ExecutionOperation]:
        """List all operations for a project, optionally filtered by status."""
        async with self._lock:
            return self._list_operations_impl(project_id, status=status)

    async def transition(
        self,
        operation_id: str,
        project_id: str,
        target: OperationStatus,
        *,
        result: dict | None = None,
        error: str | None = None,
        progress: float | None = None,
    ) -> ExecutionOperation:
        """Transition an operation to a new status."""
        async with self._lock:
            return self._transition_impl(
                operation_id, project_id, target,
                result=result, error=error, progress=progress,
            )

    async def cancel_operation(
        self,
        operation_id: str,
        project_id: str,
    ) -> ExecutionOperation:
        """Request cancellation of an operation.

        QUEUED operations are immediately CANCELLED.
        RUNNING operations transition to CANCELLING.
        Already-CANCELLING operations are returned as-is (idempotent).
        Terminal operations raise InvalidTransition.
        """
        async with self._lock:
            return self._cancel_operation_impl(operation_id, project_id)

    async def cleanup_terminal(self, project_id: str | None = None) -> int:
        """Remove expired terminal operations. Returns count removed."""
        async with self._lock:
            return self._cleanup_terminal_impl(project_id)

    def _enforce_limit(self, project_id: str) -> None:
        """Remove oldest terminal operations if over the limit.

        Note: called while lock is already held; does not acquire the lock itself.
        """
        ops = self._operations.get(project_id, {})
        if len(ops) <= self._max_per_project:
            return
        # Sort by created_at, remove oldest terminal ops first
        terminal_ops = sorted(
            [(op_id, op) for op_id, op in ops.items() if op.is_terminal],
            key=lambda x: x[1].created_at,
        )
        excess = len(ops) - self._max_per_project
        removed = 0
        for op_id, _ in terminal_ops[:excess]:
            del ops[op_id]
            removed += 1
        if removed < excess:
            logger.warning(
                "Could not enforce limit for project %s: %d active operations exceed "
                "max %d but only %d terminal ops were available to evict",
                project_id, len(ops) + removed, self._max_per_project, removed,
            )

    @property
    def total_count(self) -> int:
        """Total operations across all projects."""
        return sum(len(ops) for ops in self._operations.values())
