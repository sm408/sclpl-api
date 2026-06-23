"""Tests for Workflow API endpoints.

Covers: CRUD, SCLPLL parse/preview/apply, version management,
preflight validation, duplication, and the standard error protocol.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.models.project import DEFAULT_PROJECT_ID
from app.web.server import create_app


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


PID = DEFAULT_PROJECT_ID


# ═══════════════════════════════════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════════════════════════════════


class TestWorkflowCRUD:

    async def test_list_empty(self, client):
        resp = await client.get(f"/api/v1/projects/{PID}/workflows")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    async def test_create_workflow(self, client):
        resp = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": "Test Workflow", "description": "A test"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Test Workflow"
        assert body["description"] == "A test"
        assert body["projectId"] == PID
        assert "id" in body
        assert "createdAt" in body
        assert body["revision"] == 1
        # camelCase check
        assert "project_id" not in body
        assert "created_at" not in body
        assert "sclpll_source" not in body
        assert "sclpllSource" in body

    async def test_create_empty_name_fails(self, client):
        resp = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": ""},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_create_with_definition(self, client):
        resp = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={
                "name": "With Steps",
                "definition": {
                    "id": "wf1",
                    "name": "With Steps",
                    "description": "",
                    "steps": [{"id": "s1", "name": "s1", "type": "request", "config": {}}],
                    "variables": {},
                },
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert len(body["definition"]["steps"]) == 1

    async def test_create_with_layout(self, client):
        resp = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={
                "name": "With Layout",
                "layout": {"nodes": {"s1": {"x": 100.0, "y": 200.0}}, "viewport": {"x": 0, "y": 0, "zoom": 1}},
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["layout"]["nodes"]["s1"]["x"] == 100.0

    async def test_get_workflow(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": "Fetch Me"},
        )
        wf_id = create.json()["id"]

        resp = await client.get(f"/api/v1/projects/{PID}/workflows/{wf_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Fetch Me"

    async def test_get_not_found(self, client):
        resp = await client.get(f"/api/v1/projects/{PID}/workflows/nonexistent")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    async def test_update_workflow(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": "Old"},
        )
        wf_id = create.json()["id"]

        resp = await client.patch(
            f"/api/v1/projects/{PID}/workflows/{wf_id}",
            json={"name": "New", "description": "Updated"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "New"
        assert body["description"] == "Updated"
        assert body["revision"] == 2

    async def test_update_not_found(self, client):
        resp = await client.patch(
            f"/api/v1/projects/{PID}/workflows/nonexistent",
            json={"name": "X"},
        )
        assert resp.status_code == 404

    async def test_update_empty_body_fails(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": "Test"},
        )
        wf_id = create.json()["id"]

        resp = await client.patch(
            f"/api/v1/projects/{PID}/workflows/{wf_id}",
            json={},
        )
        assert resp.status_code == 422

    async def test_update_revision_conflict(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": "Conflict"},
        )
        wf_id = create.json()["id"]

        # First update bumps revision to 2
        await client.patch(
            f"/api/v1/projects/{PID}/workflows/{wf_id}",
            json={"name": "Update1"},
        )

        # Second update with stale revision=1
        resp = await client.patch(
            f"/api/v1/projects/{PID}/workflows/{wf_id}",
            json={"name": "Update2", "revision": 1},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "CONFLICT"

    async def test_delete_workflow(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": "Delete Me"},
        )
        wf_id = create.json()["id"]

        resp = await client.delete(f"/api/v1/projects/{PID}/workflows/{wf_id}")
        assert resp.status_code == 204

        # Confirm gone
        get_resp = await client.get(f"/api/v1/projects/{PID}/workflows/{wf_id}")
        assert get_resp.status_code == 404

    async def test_delete_not_found(self, client):
        resp = await client.delete(f"/api/v1/projects/{PID}/workflows/nonexistent")
        assert resp.status_code == 404

    async def test_duplicate_workflow(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": "Original", "description": "Original desc"},
        )
        wf_id = create.json()["id"]

        resp = await client.post(f"/api/v1/projects/{PID}/workflows/{wf_id}/duplicate")
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Original (copy)"
        assert body["id"] != wf_id
        assert body["description"] == "Original desc"

    async def test_duplicate_not_found(self, client):
        resp = await client.post(f"/api/v1/projects/{PID}/workflows/nonexistent/duplicate")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# SCLPLL Operations
# ═══════════════════════════════════════════════════════════════════════


class TestSCLPLLOperations:

    async def test_parse_valid_source(self, client):
        resp = await client.post(
            f"/api/v1/projects/{PID}/workflows/sclpll/parse",
            json={"source": '@workflow wf1 "Test"\n@step s1\n    request GET https://example.com\n'},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["definition"]["id"] == "wf1"
        assert body["sourceHash"]
        assert body["diagnostics"] == []

    async def test_parse_invalid_source(self, client):
        resp = await client.post(
            f"/api/v1/projects/{PID}/workflows/sclpll/parse",
            json={"source": "invalid source"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert len(body["diagnostics"]) >= 1
        assert body["diagnostics"][0]["severity"] == "error"

    async def test_preview_sclpll(self, client):
        resp = await client.post(
            f"/api/v1/projects/{PID}/workflows/sclpll/preview",
            json={"source": '@workflow wf1\n@step s1\n    request GET https://example.com\n'},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["definition"] is not None
        assert body["sclpllSource"]

    async def test_preview_with_workflow_id(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": "Test"},
        )
        wf_id = create.json()["id"]

        resp = await client.post(
            f"/api/v1/projects/{PID}/workflows/sclpll/preview",
            json={"source": f'@workflow {wf_id}\n@step s1\n    request GET https://example.com\n'},
            params={"workflow_id": wf_id},
        )
        assert resp.status_code == 200

    async def test_apply_sclpll(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": "Test"},
        )
        wf_id = create.json()["id"]

        resp = await client.post(
            f"/api/v1/projects/{PID}/workflows/{wf_id}/sclpll/apply",
            json={"source": f'@workflow {wf_id} "Updated"\n@step s1\n    request GET https://example.com\n'},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["definition"]["steps"]) == 1
        assert body["sclpllSource"]

    async def test_apply_sclpll_not_found(self, client):
        resp = await client.post(
            f"/api/v1/projects/{PID}/workflows/nonexistent/sclpll/apply",
            json={"source": "@workflow wf1\n"},
        )
        assert resp.status_code == 404

    async def test_apply_sclpll_invalid_source(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": "Test"},
        )
        wf_id = create.json()["id"]

        resp = await client.post(
            f"/api/v1/projects/{PID}/workflows/{wf_id}/sclpll/apply",
            json={"source": "invalid source"},
        )
        assert resp.status_code == 422

    async def test_generate_sclpll(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={
                "name": "Test",
                "definition": {
                    "id": "wf1",
                    "name": "Test",
                    "description": "",
                    "steps": [
                        {
                            "id": "s1",
                            "name": "s1",
                            "type": "request",
                            "config": {"inline_request": {"method": "GET", "url": "https://example.com", "headers": {}}},
                        }
                    ],
                    "variables": {},
                },
            },
        )
        wf_id = create.json()["id"]

        resp = await client.post(f"/api/v1/projects/{PID}/workflows/{wf_id}/sclpll/generate")
        assert resp.status_code == 200
        body = resp.json()
        # The endpoint returns a raw dict with sclpll_source key
        source = body.get("sclpllSource") or body.get("sclpll_source", "")
        assert "@workflow" in source

    async def test_generate_not_found(self, client):
        resp = await client.post(f"/api/v1/projects/{PID}/workflows/nonexistent/sclpll/generate")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Preflight Validation
# ═══════════════════════════════════════════════════════════════════════


class TestPreflightValidation:

    async def test_validate_workflow(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={
                "name": "Valid",
                "definition": {
                    "id": "wf1",
                    "name": "Valid",
                    "description": "",
                    "steps": [
                        {"id": "s1", "type": "request", "config": {}},
                        {"id": "s2", "type": "request", "config": {}, "depends_on": ["s1"]},
                    ],
                    "variables": {},
                },
            },
        )
        wf_id = create.json()["id"]

        resp = await client.post(f"/api/v1/projects/{PID}/workflows/{wf_id}/validate")
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True

    async def test_validate_with_circular_deps(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={
                "name": "Circular",
                "definition": {
                    "id": "wf1",
                    "name": "Circular",
                    "description": "",
                    "steps": [
                        {"id": "a", "type": "request", "config": {}, "depends_on": ["b"]},
                        {"id": "b", "type": "request", "config": {}, "depends_on": ["a"]},
                    ],
                    "variables": {},
                },
            },
        )
        wf_id = create.json()["id"]

        resp = await client.post(f"/api/v1/projects/{PID}/workflows/{wf_id}/validate")
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is False
        assert len(body["issues"]) >= 1

    async def test_validate_not_found(self, client):
        resp = await client.post(f"/api/v1/projects/{PID}/workflows/nonexistent/validate")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Versions
# ═══════════════════════════════════════════════════════════════════════


class TestVersionManagement:

    async def test_save_version(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": "Test"},
        )
        wf_id = create.json()["id"]

        resp = await client.post(
            f"/api/v1/projects/{PID}/workflows/{wf_id}/versions",
            json={"description": "v1", "author": "tester"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["version"] == 1
        assert body["description"] == "v1"
        assert body["author"] == "tester"
        assert body["workflowId"] == wf_id

    async def test_list_versions(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": "Test"},
        )
        wf_id = create.json()["id"]

        await client.post(
            f"/api/v1/projects/{PID}/workflows/{wf_id}/versions",
            json={"description": "v1"},
        )
        await client.post(
            f"/api/v1/projects/{PID}/workflows/{wf_id}/versions",
            json={"description": "v2"},
        )

        resp = await client.get(f"/api/v1/projects/{PID}/workflows/{wf_id}/versions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2

    async def test_get_version(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": "Test"},
        )
        wf_id = create.json()["id"]

        await client.post(
            f"/api/v1/projects/{PID}/workflows/{wf_id}/versions",
            json={"description": "v1"},
        )

        resp = await client.get(f"/api/v1/projects/{PID}/workflows/{wf_id}/versions/1")
        assert resp.status_code == 200
        assert resp.json()["version"] == 1

    async def test_get_version_not_found(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": "Test"},
        )
        wf_id = create.json()["id"]

        resp = await client.get(f"/api/v1/projects/{PID}/workflows/{wf_id}/versions/999")
        assert resp.status_code == 404

    async def test_restore_version(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": "Original"},
        )
        wf_id = create.json()["id"]

        await client.post(
            f"/api/v1/projects/{PID}/workflows/{wf_id}/versions",
            json={"description": "v1"},
        )

        # Change the workflow
        await client.patch(
            f"/api/v1/projects/{PID}/workflows/{wf_id}",
            json={"name": "Changed"},
        )

        # Restore to v1
        resp = await client.post(
            f"/api/v1/projects/{PID}/workflows/{wf_id}/versions/restore",
            json={"version": 1},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Original"

    async def test_restore_not_found(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": "Test"},
        )
        wf_id = create.json()["id"]

        resp = await client.post(
            f"/api/v1/projects/{PID}/workflows/{wf_id}/versions/restore",
            json={"version": 999},
        )
        assert resp.status_code == 404

    async def test_compare_versions(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": "Test"},
        )
        wf_id = create.json()["id"]

        await client.post(
            f"/api/v1/projects/{PID}/workflows/{wf_id}/versions",
            json={"description": "v1"},
        )
        await client.patch(
            f"/api/v1/projects/{PID}/workflows/{wf_id}",
            json={"name": "Changed"},
        )
        await client.post(
            f"/api/v1/projects/{PID}/workflows/{wf_id}/versions",
            json={"description": "v2"},
        )

        resp = await client.post(
            f"/api/v1/projects/{PID}/workflows/{wf_id}/versions/compare",
            json={"versionA": 1, "versionB": 2},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "diff" in body

    async def test_compare_not_found(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": "Test"},
        )
        wf_id = create.json()["id"]

        resp = await client.post(
            f"/api/v1/projects/{PID}/workflows/{wf_id}/versions/compare",
            json={"versionA": 1, "versionB": 2},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# camelCase and Error Protocol
# ═══════════════════════════════════════════════════════════════════════


class TestCamelCaseAndErrors:

    async def test_response_uses_camel_case(self, client):
        resp = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": "CamelTest"},
        )
        body = resp.json()
        assert "projectId" in body
        assert "project_id" not in body
        assert "createdAt" in body
        assert "created_at" not in body
        assert "updatedAt" in body
        assert "updated_at" not in body
        assert "sclpllSource" in body
        assert "sclpll_source" not in body

    async def test_version_response_camel_case(self, client):
        create = await client.post(
            f"/api/v1/projects/{PID}/workflows",
            json={"name": "Test"},
        )
        wf_id = create.json()["id"]

        resp = await client.post(
            f"/api/v1/projects/{PID}/workflows/{wf_id}/versions",
            json={"description": "v1"},
        )
        body = resp.json()
        assert "workflowId" in body
        assert "workflow_id" not in body
        assert "createdAt" in body
        assert "created_at" not in body

    async def test_error_response_standard_shape(self, client):
        resp = await client.get(f"/api/v1/projects/{PID}/workflows/nonexistent")
        body = resp.json()
        assert "error" in body
        err = body["error"]
        assert "code" in err
        assert "message" in err
        assert "fieldErrors" in err
        assert "correlationId" in err
