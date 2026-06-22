"""Tests for Operations API endpoints.

Covers: operations CRUD, cancellation, and error handling.
SSE streaming is tested via unit tests in test_operations.py.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.models.operation import OperationStatus, OperationType
from app.web.server import create_app
from app.web.sse import EventType

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
async def app(tmp_path):
    """Create a fresh app with an in-memory database."""
    db_path = str(tmp_path / "test.db")
    application = create_app(db_path)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app):
    """Async test client bound to the app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8420") as c:
        yield c


@pytest.fixture
def default_project_id():
    """The well-known default project ID."""
    from app.core.models.project import DEFAULT_PROJECT_ID

    return DEFAULT_PROJECT_ID


# ── Operations API ──────────────────────────────────────────────────────


class TestOperationsAPI:
    """Test operations REST endpoints."""

    @pytest.mark.asyncio
    async def test_list_operations_empty(self, client, default_project_id):
        resp = await client.get(
            "/api/v1/operations",
            params={"project_id": default_project_id},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    @pytest.mark.asyncio
    async def test_list_operations_with_data(self, app, client, default_project_id):
        registry = app.state.services.operations
        registry.create_operation(default_project_id, OperationType.WORKFLOW_RUN)
        registry.create_operation(default_project_id, OperationType.BATCH_RUN)

        resp = await client.get(
            "/api/v1/operations",
            params={"project_id": default_project_id},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    @pytest.mark.asyncio
    async def test_list_operations_filter_by_status(self, app, client, default_project_id):
        registry = app.state.services.operations
        op1 = registry.create_operation(default_project_id, OperationType.WORKFLOW_RUN)
        registry.create_operation(default_project_id, OperationType.BATCH_RUN)
        registry.transition(op1.id, default_project_id, OperationStatus.RUNNING)

        resp = await client.get(
            "/api/v1/operations",
            params={"project_id": default_project_id, "status": "running"},
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["status"] == "running"

    @pytest.mark.asyncio
    async def test_get_operation(self, app, client, default_project_id):
        registry = app.state.services.operations
        op = registry.create_operation(default_project_id, OperationType.WORKFLOW_RUN)

        resp = await client.get(f"/api/v1/operations/{op.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == op.id
        assert body["projectId"] == default_project_id
        assert body["status"] == "queued"

    @pytest.mark.asyncio
    async def test_get_operation_not_found(self, client):
        resp = await client.get("/api/v1/operations/nonexistent")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_cancel_queued_operation(self, app, client, default_project_id):
        registry = app.state.services.operations
        op = registry.create_operation(default_project_id, OperationType.WORKFLOW_RUN)

        resp = await client.delete(f"/api/v1/operations/{op.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_running_operation(self, app, client, default_project_id):
        registry = app.state.services.operations
        op = registry.create_operation(default_project_id, OperationType.WORKFLOW_RUN)
        registry.transition(op.id, default_project_id, OperationStatus.RUNNING)

        resp = await client.delete(f"/api/v1/operations/{op.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "cancelling"

    @pytest.mark.asyncio
    async def test_cancel_terminal_operation_fails(self, app, client, default_project_id):
        registry = app.state.services.operations
        op = registry.create_operation(default_project_id, OperationType.WORKFLOW_RUN)
        registry.transition(op.id, default_project_id, OperationStatus.RUNNING)
        registry.transition(op.id, default_project_id, OperationStatus.SUCCEEDED)

        resp = await client.delete(f"/api/v1/operations/{op.id}")
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "CONFLICT"

    @pytest.mark.asyncio
    async def test_cancel_not_found(self, client):
        resp = await client.delete("/api/v1/operations/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_operation_camel_case(self, app, client, default_project_id):
        registry = app.state.services.operations
        op = registry.create_operation(default_project_id, OperationType.WORKFLOW_RUN)
        registry.transition(op.id, default_project_id, OperationStatus.RUNNING)

        resp = await client.get(f"/api/v1/operations/{op.id}")
        body = resp.json()
        assert "projectId" in body
        assert "project_id" not in body
        assert "startedAt" in body
        assert "started_at" not in body

    @pytest.mark.asyncio
    async def test_operation_with_result(self, app, client, default_project_id):
        registry = app.state.services.operations
        op = registry.create_operation(default_project_id, OperationType.WORKFLOW_RUN)
        registry.transition(op.id, default_project_id, OperationStatus.RUNNING)
        registry.transition(
            op.id,
            default_project_id,
            OperationStatus.SUCCEEDED,
            result={"output": "done"},
        )

        resp = await client.get(f"/api/v1/operations/{op.id}")
        body = resp.json()
        assert body["result"] == {"output": "done"}
        assert body["progress"] == 1.0

    @pytest.mark.asyncio
    async def test_operation_with_error(self, app, client, default_project_id):
        registry = app.state.services.operations
        op = registry.create_operation(default_project_id, OperationType.WORKFLOW_RUN)
        registry.transition(op.id, default_project_id, OperationStatus.RUNNING)
        registry.transition(
            op.id,
            default_project_id,
            OperationStatus.FAILED,
            error="Something broke",
        )

        resp = await client.get(f"/api/v1/operations/{op.id}")
        body = resp.json()
        assert body["error"] == "Something broke"

    @pytest.mark.asyncio
    async def test_sse_endpoint_registered(self, client, default_project_id):
        """Verify the SSE endpoint is listed in OpenAPI spec."""
        resp = await client.get("/openapi.json")
        paths = resp.json().get("paths", {})
        assert "/api/v1/operations/events/stream" in paths


# ── Operation Lifecycle with SSE ─────────────────────────────────────────


class TestOperationLifecycleWithSSE:
    """Test complete operation lifecycle with SSE events."""

    @pytest.mark.asyncio
    async def test_create_and_complete_operation_with_events(
        self, app, client, default_project_id
    ):
        """Test creating an operation and verifying SSE events are emitted."""
        registry = app.state.services.operations
        sse_manager = app.state.services.sse

        # Create operation
        op = registry.create_operation(default_project_id, OperationType.WORKFLOW_RUN)

        # Simulate lifecycle with events
        from app.web.sse import EventType, OperationCompletedData, OperationStartedData, StreamEvent

        started_event = StreamEvent.create(
            project_id=default_project_id,
            event_type=EventType.OPERATION_STARTED,
            data=OperationStartedData(op.id, default_project_id, "workflow_run"),
            operation_id=op.id,
            sequence=sse_manager.replay_buffer.next_sequence(default_project_id),
        )
        await sse_manager.publish(started_event)

        # Transition to running
        registry.transition(op.id, default_project_id, OperationStatus.RUNNING)

        # Complete
        registry.transition(
            op.id,
            default_project_id,
            OperationStatus.SUCCEEDED,
            result={"output": "done"},
        )

        completed_event = StreamEvent.create(
            project_id=default_project_id,
            event_type=EventType.OPERATION_COMPLETED,
            data=OperationCompletedData(op.id, default_project_id, {"output": "done"}),
            operation_id=op.id,
            sequence=sse_manager.replay_buffer.next_sequence(default_project_id),
        )
        await sse_manager.publish(completed_event)

        # Verify operation state
        resp = await client.get(f"/api/v1/operations/{op.id}")
        body = resp.json()
        assert body["status"] == "succeeded"
        assert body["result"] == {"output": "done"}

        # Verify events in replay buffer
        events = sse_manager.get_replay_events(default_project_id, None)
        assert len(events) == 2
        assert events[0].event == EventType.OPERATION_STARTED
        assert events[1].event == EventType.OPERATION_COMPLETED

    @pytest.mark.asyncio
    async def test_cancel_operation_emits_event(
        self, app, client, default_project_id
    ):
        """Test that cancelling an operation emits the right event."""
        registry = app.state.services.operations
        sse_manager = app.state.services.sse

        # Create and start operation
        op = registry.create_operation(default_project_id, OperationType.WORKFLOW_RUN)
        registry.transition(op.id, default_project_id, OperationStatus.RUNNING)

        # Cancel via API (which should emit event)
        resp = await client.delete(f"/api/v1/operations/{op.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelling"

        # Verify cancellation event in buffer
        events = sse_manager.get_replay_events(default_project_id, None)
        assert len(events) == 1
        assert events[0].event == EventType.OPERATION_CANCELLED


# ── Error Handling ──────────────────────────────────────────────────────


class TestOperationErrors:
    """Test error handling in operations API."""

    @pytest.mark.asyncio
    async def test_invalid_status_filter(self, client, default_project_id):
        """Test that invalid status filter returns empty results."""
        resp = await client.get(
            "/api/v1/operations",
            params={"project_id": default_project_id, "status": "invalid"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    @pytest.mark.asyncio
    async def test_operation_not_found_error_shape(self, client):
        """Test that 404 errors follow the standard error envelope."""
        resp = await client.get("/api/v1/operations/nonexistent")
        assert resp.status_code == 404
        body = resp.json()
        assert "error" in body
        err = body["error"]
        assert err["code"] == "NOT_FOUND"
        assert "message" in err
        assert "correlationId" in err

    @pytest.mark.asyncio
    async def test_cancel_terminal_error_shape(self, app, client, default_project_id):
        """Test that cancellation conflict errors follow the standard envelope."""
        registry = app.state.services.operations
        op = registry.create_operation(default_project_id, OperationType.WORKFLOW_RUN)
        registry.transition(op.id, default_project_id, OperationStatus.RUNNING)
        registry.transition(op.id, default_project_id, OperationStatus.SUCCEEDED)

        resp = await client.delete(f"/api/v1/operations/{op.id}")
        assert resp.status_code == 409
        body = resp.json()
        assert "error" in body
        err = body["error"]
        assert err["code"] == "CONFLICT"
        assert "cannot cancel" in err["message"].lower()
