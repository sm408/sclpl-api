"""Tests for the FastAPI web API foundation.

Covers: lifecycle, health, projects CRUD, camelCase aliases, error
protocol, validation, host/origin rejection, shutdown, correlation IDs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.models.project import DEFAULT_PROJECT_ID
from app.web.server import CORRELATION_ID_HEADER, create_app  # noqa: I001

# ── Fixtures ────────────────────────────────────────────────────────────

_SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "openapi_snapshot.json"


@pytest.fixture
def snapshot_path() -> Path:
    """Return the path to the committed OpenAPI snapshot file."""
    return _SNAPSHOT_PATH


@pytest.fixture
async def app(tmp_path):
    """Create a fresh app with an in-memory database."""
    db_path = str(tmp_path / "test.db")
    application = create_app(db_path)
    # Manually trigger lifespan so we can use it in tests
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app):
    """Async test client bound to the app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8420") as c:
        yield c


# ── Lifecycle ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lifespan_startup_creates_database(app):
    """After lifespan startup, app.state.db should be initialised."""
    assert hasattr(app.state, "db")
    assert hasattr(app.state, "services")
    assert hasattr(app.state, "event_bus")


@pytest.mark.asyncio
async def test_lifespan_default_project_exists(app):
    """The default project should be created during database init."""
    projects = await app.state.services.projects.list_all()
    ids = [p.id for p in projects]
    assert DEFAULT_PROJECT_ID in ids


# ── Health ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
    assert body["schemaVersion"] == 5


@pytest.mark.asyncio
async def test_health_uses_camel_case(client):
    """schema_version must appear as schemaVersion in JSON."""
    resp = await client.get("/health")
    assert "schemaVersion" in resp.json()
    assert "schema_version" not in resp.json()


# ── Security headers ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_security_headers_present(client):
    resp = await client.get("/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in resp.headers


# ── Host validation ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reject_bad_host_header(client):
    """Requests with a non-localhost Host header are rejected."""
    resp = await client.get("/health", headers={"host": "evil.com"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "BAD_REQUEST"


@pytest.mark.asyncio
async def test_accept_localhost_host(client):
    resp = await client.get("/health", headers={"host": "localhost:8420"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_accept_127_host(client):
    resp = await client.get("/health", headers={"host": "127.0.0.1:8420"})
    assert resp.status_code == 200


# ── Loopback-only for /docs ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_docs_accessible_from_loopback(client):
    """ASGI test client has host 127.0.0.1 — /docs should work."""
    resp = await client.get("/docs")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_openapi_accessible_from_loopback(client):
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    assert "openapi" in resp.json()


# ── Projects — list ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_projects_returns_paginated(client):
    resp = await client.get("/api/v1/projects")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert "nextCursor" in body
    assert isinstance(body["items"], list)
    assert body["total"] >= 1  # at least the Default project


@pytest.mark.asyncio
async def test_list_projects_contains_default(client):
    resp = await client.get("/api/v1/projects")
    items = resp.json()["items"]
    ids = [p["id"] for p in items]
    assert DEFAULT_PROJECT_ID in ids


# ── Projects — create ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_project(client):
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "Test Project", "description": "A test"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Test Project"
    assert body["description"] == "A test"
    assert body["isDefault"] is False
    assert "id" in body
    assert "createdAt" in body


@pytest.mark.asyncio
async def test_create_project_camel_case_response(client):
    """Response keys must be camelCase."""
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "CamelTest"},
    )
    body = resp.json()
    assert "isDefault" in body
    assert "is_default" not in body
    assert "createdAt" in body
    assert "created_at" not in body
    assert "rootPath" in body
    assert "root_path" not in body


@pytest.mark.asyncio
async def test_create_project_empty_name_fails(client):
    resp = await client.post(
        "/api/v1/projects",
        json={"name": ""},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_create_project_missing_name_fails(client):
    """Missing required field must return the standard error envelope."""
    resp = await client.post(
        "/api/v1/projects",
        json={"description": "no name"},
    )
    assert resp.status_code == 422
    body = resp.json()
    # Verify the full {error: {code, message, fieldErrors, correlationId}} envelope
    assert "error" in body
    err = body["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert isinstance(err["message"], str) and len(err["message"]) > 0
    assert isinstance(err["fieldErrors"], list)
    assert len(err["fieldErrors"]) > 0
    # At least one field error should reference "name"
    field_names = [fe["field"] for fe in err["fieldErrors"]]
    assert any("name" in fn for fn in field_names), (
        f"Expected a 'name' field error, got: {err['fieldErrors']}"
    )
    assert "correlationId" in err
    assert isinstance(err["correlationId"], str) and len(err["correlationId"]) > 0


# ── Projects — get ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_project(client):
    # Create first
    create_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Fetch Me"},
    )
    pid = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/projects/{pid}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Fetch Me"


@pytest.mark.asyncio
async def test_get_project_not_found(client):
    resp = await client.get("/api/v1/projects/nonexistent-id")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "NOT_FOUND"


# ── Projects — update ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_project(client):
    create_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Old Name"},
    )
    pid = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/projects/{pid}",
        json={"name": "New Name", "description": "Updated"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"
    assert resp.json()["description"] == "Updated"


@pytest.mark.asyncio
async def test_update_default_project_fails(client):
    resp = await client.patch(
        f"/api/v1/projects/{DEFAULT_PROJECT_ID}",
        json={"name": "Hacked"},
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_update_project_not_found(client):
    resp = await client.patch(
        "/api/v1/projects/nonexistent-id",
        json={"name": "X"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_project_empty_body_fails(client):
    create_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Some"},
    )
    pid = create_resp.json()["id"]

    resp = await client.patch(f"/api/v1/projects/{pid}", json={})
    assert resp.status_code == 422


# ── Projects — delete ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_project(client):
    create_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Delete Me"},
    )
    pid = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/projects/{pid}")
    assert resp.status_code == 204

    # Confirm gone
    get_resp = await client.get(f"/api/v1/projects/{pid}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_default_project_fails(client):
    resp = await client.delete(f"/api/v1/projects/{DEFAULT_PROJECT_ID}")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_delete_project_not_found(client):
    resp = await client.delete("/api/v1/projects/nonexistent-id")
    assert resp.status_code == 404


# ── Error protocol ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_error_response_has_standard_shape(client):
    """All errors must follow {error: {code, message, fieldErrors, correlationId}}."""
    resp = await client.get("/api/v1/projects/nonexistent")
    body = resp.json()
    assert "error" in body
    err = body["error"]
    assert "code" in err
    assert "message" in err
    assert "fieldErrors" in err
    assert "correlationId" in err
    # camelCase check
    assert "field_errors" not in err
    assert "correlation_id" not in err


@pytest.mark.asyncio
async def test_validation_error_has_field_errors(client):
    resp = await client.post(
        "/api/v1/projects",
        json={"name": ""},
    )
    body = resp.json()
    err = body["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert isinstance(err["fieldErrors"], list)


# ── API routes return JSON, not caught by any fallback ─────────────────


@pytest.mark.asyncio
async def test_api_routes_return_json(client):
    """API routes should return proper JSON, not HTML."""
    resp = await client.get("/api/v1/projects")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")


@pytest.mark.asyncio
async def test_health_returns_json(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")


@pytest.mark.asyncio
async def test_unknown_api_route_returns_404(client):
    """Unknown API routes should get a 404 JSON error."""
    resp = await client.get("/api/v1/nonexistent")
    assert resp.status_code == 404


# ── Correlation ID ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_correlation_id_generated_when_not_provided(client):
    """Every response should include an X-Correlation-ID header."""
    resp = await client.get("/health")
    assert CORRELATION_ID_HEADER in resp.headers
    cid = resp.headers[CORRELATION_ID_HEADER]
    assert len(cid) == 12  # uuid4 hex truncated to 12 chars


@pytest.mark.asyncio
async def test_correlation_id_echoed_from_request(client):
    """When the client sends X-Correlation-ID, it should be echoed back."""
    resp = await client.get(
        "/health",
        headers={CORRELATION_ID_HEADER: "my-test-cid-1"},
    )
    assert resp.headers[CORRELATION_ID_HEADER] == "my-test-cid-1"


@pytest.mark.asyncio
async def test_correlation_id_in_error_response(client):
    """Error responses should carry the same correlation ID as the request."""
    resp = await client.get(
        "/api/v1/projects/nonexistent",
        headers={CORRELATION_ID_HEADER: "err-cid-test"},
    )
    body = resp.json()
    assert body["error"]["correlationId"] == "err-cid-test"


@pytest.mark.asyncio
async def test_correlation_id_in_validation_error(client):
    """Validation errors should use the request's correlation ID."""
    resp = await client.post(
        "/api/v1/projects",
        json={"description": "no name"},
        headers={CORRELATION_ID_HEADER: "val-cid-test"},
    )
    body = resp.json()
    assert body["error"]["correlationId"] == "val-cid-test"


# ── OpenAPI ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_openapi_has_projects_paths(client):
    resp = await client.get("/openapi.json")
    spec = resp.json()
    paths = spec.get("paths", {})
    assert "/api/v1/projects" in paths
    assert "/api/v1/projects/{project_id}" in paths
    assert "/health" in paths


@pytest.mark.asyncio
async def test_openapi_version_matches(client):
    resp = await client.get("/openapi.json")
    spec = resp.json()
    assert spec["info"]["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_openapi_snapshot_matches(client, snapshot_path):
    """The OpenAPI spec must match the committed snapshot.

    If this test fails, run ``python scripts/generate_openapi_snapshot.py``
    and commit the updated snapshot.
    """
    resp = await client.get("/openapi.json")
    actual = resp.json()
    actual_str = json.dumps(actual, indent=2, sort_keys=True)

    if not snapshot_path.exists():
        pytest.fail(
            f"OpenAPI snapshot not found at {snapshot_path}. "
            "Run: python scripts/generate_openapi_snapshot.py"
        )

    expected_str = snapshot_path.read_text(encoding="utf-8").rstrip("\n")
    assert actual_str == expected_str, (
        "OpenAPI spec has drifted from the snapshot. "
        "If the change is intentional, run: "
        "python scripts/generate_openapi_snapshot.py"
    )


# ── Shutdown ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lifespan_shutdown_closes_database(tmp_path):
    """Verify the lifespan context manager closes the database on exit."""
    db_path = str(tmp_path / "shutdown_test.db")
    application = create_app(db_path)

    # Enter and exit lifespan
    async with application.router.lifespan_context(application):
        assert application.state.db._db is not None

    # After exit, the connection should be closed
    assert application.state.db._db is None
