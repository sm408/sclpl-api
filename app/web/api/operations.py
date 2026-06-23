"""Operations API routes and SSE event streaming.

Provides endpoints for listing, getting, and cancelling operations,
plus an SSE endpoint for real-time event streaming.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.core.models.operation import InvalidTransition, OperationStatus
from app.services.operation_registry import (
    OperationNotFoundError,
    OperationRegistry,
)
from app.web.deps import _get_operation_registry, _get_sse_manager
from app.web.errors import ConflictError, NotFoundError
from app.web.sse import (
    EventType,
    OperationCancelledData,
    SSEManager,
    StreamEvent,
    StreamResetData,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/operations", tags=["operations"])


# ── Operations CRUD ──────────────────────────────────────────────────────


@router.get("", response_model=dict[str, Any])
async def list_operations(
    project_id: str | None = None,
    status: str | None = None,
    registry: OperationRegistry = Depends(_get_operation_registry),  # noqa: B008
) -> dict[str, Any]:
    """List operations, optionally filtered by project and status."""
    status_filter = None
    if status:
        try:
            status_filter = OperationStatus(status)
        except ValueError:
            return {"items": [], "total": 0}

    if project_id:
        ops = await registry.list_operations(project_id, status=status_filter)
    else:
        return {"items": [], "total": 0}

    items = [op.to_dict() for op in ops]
    return {"items": items, "total": len(items)}


@router.get("/{operation_id}", response_model=dict[str, Any])
async def get_operation(
    operation_id: str,
    project_id: str | None = None,
    registry: OperationRegistry = Depends(_get_operation_registry),  # noqa: B008
) -> dict[str, Any]:
    """Get a single operation by ID."""
    try:
        if project_id:
            op = await registry.get_operation(operation_id, project_id)
        else:
            op = await registry.get_operation_any_project(operation_id)
        return op.to_dict()
    except OperationNotFoundError as err:
        raise NotFoundError(
            message=f"Operation '{operation_id}' not found."
        ) from err


@router.delete("/{operation_id}", response_model=dict[str, Any])
async def cancel_operation(
    operation_id: str,
    project_id: str | None = None,
    registry: OperationRegistry = Depends(_get_operation_registry),  # noqa: B008
    sse_manager: SSEManager = Depends(_get_sse_manager),  # noqa: B008
) -> dict[str, Any]:
    """Cancel an operation.

    QUEUED operations are immediately CANCELLED.
    RUNNING operations transition to CANCELLING.
    Terminal operations cannot be cancelled.
    """
    try:
        if project_id:
            op = await registry.cancel_operation(operation_id, project_id)
        else:
            op = await registry.get_operation_any_project(operation_id)
            op = await registry.cancel_operation(operation_id, op.project_id)

        # Emit cancellation event
        event = StreamEvent.create(
            project_id=op.project_id,
            event_type=EventType.OPERATION_CANCELLED,
            data=OperationCancelledData(
                operation_id=op.id,
                project_id=op.project_id,
            ),
            operation_id=op.id,
            sequence=sse_manager.replay_buffer.next_sequence(
                op.project_id
            ),
        )
        await sse_manager.publish(event)

        return op.to_dict()
    except OperationNotFoundError as err:
        raise NotFoundError(
            message=f"Operation '{operation_id}' not found."
        ) from err
    except InvalidTransition as err:
        raise ConflictError(
            message=f"Cannot cancel operation in {err.current.value} status."
        ) from err


# ── SSE Event Stream ─────────────────────────────────────────────────────


@router.get("/events/stream")
async def stream_events(
    request: Request,
    project_id: str,
    last_event_id: str | None = None,
    sse_manager: SSEManager = Depends(_get_sse_manager),  # noqa: B008
) -> StreamingResponse:
    """SSE endpoint for real-time event streaming.

    Clients connect with a project_id to receive events for that project.
    Supports Last-Event-ID header for reconnection replay.
    """
    header_last_id = request.headers.get("last-event-id")
    if header_last_id:
        last_event_id = header_last_id

    async def event_generator():
        # Send replay events if reconnecting
        if last_event_id:
            replay = sse_manager.get_replay_events(
                project_id, last_event_id
            )
            needs_reset = not replay
            if needs_reset:
                reset_event = StreamEvent.create(
                    project_id=project_id,
                    event_type=EventType.STREAM_RESET,
                    data=StreamResetData(
                        reason="Replay impossible: event not in buffer"
                    ),
                    sequence=sse_manager.replay_buffer.next_sequence(
                        project_id
                    ),
                )
                yield reset_event.to_sse()
            else:
                for event in replay:
                    yield event.to_sse()

        # Subscribe to new events
        queue = sse_manager.subscribe(project_id)
        await sse_manager.start_heartbeat(project_id, queue)

        try:
            while True:
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=1.0
                    )
                    if event is None:
                        yield ": heartbeat\n\n"
                    else:
                        yield event.to_sse()
                except TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            await sse_manager.stop_heartbeat(project_id, queue)
            sse_manager.unsubscribe(project_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
