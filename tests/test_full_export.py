from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.core.models.project import DEFAULT_PROJECT_ID
from app.services.full_export_service import FullExportService
from app.services.full_import_service import FullImportService
from app.storage.db import Database


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
async def populated_db(db):
    now = "2026-01-01T00:00:00Z"
    await db.execute(
        "INSERT INTO collections (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("col-1", "Test Collection", "A test collection", now, now),
    )
    await db.execute(
        """INSERT INTO requests (id, name, method, url, headers, query_params, body, body_type, auth_type, auth_config, collection_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("req-1", "Get Users", "GET", "https://api.example.com/users", "[]", "[]", None, None, None, "{}", "col-1", now, now),
    )
    await db.execute(
        "INSERT INTO environments (id, name, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("env-1", "Development", 1, now, now),
    )
    await db.execute(
        "INSERT INTO variables (environment_id, key, value, scope, is_secret, enabled) VALUES (?, ?, ?, ?, ?, ?)",
        ("env-1", "BASE_URL", "https://dev.example.com", "environment", 0, 1),
    )
    await db.execute(
        """INSERT INTO history (id, request_id, request_name, method, url, status, status_code, response_body, response_headers, duration_ms, error_message, environment_id, variables_used, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("hist-1", "req-1", "Get Users", "GET", "https://api.example.com/users", "success", 200, '{"users":[]}', "{}", 150, None, "env-1", "{}", now),
    )
    await db.execute(
        "INSERT INTO workflows (id, name, description, steps, variables, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("wf-1", "Test Workflow", "A test workflow", "[]", "{}", now, now),
    )
    await db.commit()
    return db


@pytest.mark.asyncio
async def test_export_all_creates_structure(populated_db, tmp_path):
    exporter = FullExportService(populated_db)
    base = await exporter.export_all(tmp_path / "export")

    assert (base / "manifest.json").exists()
    assert (base / "import.py").exists()
    assert (base / "projects").is_dir()
    assert (base / "workflows").is_dir()
    assert (base / "functions").is_dir()
    assert (base / "plugins").is_dir()
    assert (base / "history").is_dir()
    assert (base / "environments").is_dir()
    assert (base / "collections").is_dir()
    assert (base / "database").is_dir()

    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["format"] == "sclplapi-full-export"
    assert manifest["version"] == 1
    assert "export_id" in manifest


@pytest.mark.asyncio
async def test_export_workflows(populated_db, tmp_path):
    exporter = FullExportService(populated_db)
    count = await exporter.export_workflows(tmp_path / "wf")
    assert count == 1
    assert (tmp_path / "wf" / "Test Workflow.json").exists()

    data = json.loads((tmp_path / "wf" / "Test Workflow.json").read_text(encoding="utf-8"))
    assert data["name"] == "Test Workflow"
    assert data["id"] == "wf-1"


@pytest.mark.asyncio
async def test_export_history(populated_db, tmp_path):
    exporter = FullExportService(populated_db)
    count = await exporter.export_history(tmp_path / "hist")
    assert count == 1
    assert (tmp_path / "hist" / "history.json").exists()

    data = json.loads((tmp_path / "hist" / "history.json").read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["id"] == "hist-1"


@pytest.mark.asyncio
async def test_export_environments(populated_db, tmp_path):
    exporter = FullExportService(populated_db)
    count = await exporter.export_environments(tmp_path / "env")
    assert count == 1
    assert (tmp_path / "env" / "environments.json").exists()

    data = json.loads((tmp_path / "env" / "environments.json").read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["name"] == "Development"
    assert len(data[0]["variables"]) == 1


@pytest.mark.asyncio
async def test_export_collections(populated_db, tmp_path):
    exporter = FullExportService(populated_db)
    count = await exporter.export_collections(tmp_path / "col")
    assert count == 1
    assert (tmp_path / "col" / "collections.json").exists()

    data = json.loads((tmp_path / "col" / "collections.json").read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["name"] == "Test Collection"
    assert len(data[0]["requests"]) == 1


@pytest.mark.asyncio
async def test_export_empty_db(db, tmp_path):
    exporter = FullExportService(db)
    base = await exporter.export_all(tmp_path / "empty")
    assert (base / "manifest.json").exists()


@pytest.mark.asyncio
async def test_import_history(populated_db, tmp_path):
    exporter = FullExportService(populated_db)
    export_dir = tmp_path / "export"
    await exporter.export_all(export_dir)

    fresh_db = Database(":memory:")
    await fresh_db.connect()
    await fresh_db.initialize()

    importer = FullImportService(fresh_db)
    count = await importer.import_history(export_dir)
    assert count == 1

    rows = await fresh_db.fetch_all("SELECT * FROM history")
    assert len(rows) == 1
    assert rows[0]["id"] == "hist-1"
    await fresh_db.close()


@pytest.mark.asyncio
async def test_import_environments(populated_db, tmp_path):
    exporter = FullExportService(populated_db)
    export_dir = tmp_path / "export"
    await exporter.export_all(export_dir)

    fresh_db = Database(":memory:")
    await fresh_db.connect()
    await fresh_db.initialize()

    importer = FullImportService(fresh_db)
    count = await importer.import_environments(export_dir)
    assert count == 1

    envs = await fresh_db.fetch_all("SELECT * FROM environments")
    assert len(envs) == 1
    assert envs[0]["name"] == "Development"

    vars_rows = await fresh_db.fetch_all("SELECT * FROM variables WHERE environment_id = ?", ("env-1",))
    assert len(vars_rows) == 1
    assert vars_rows[0]["key"] == "BASE_URL"
    await fresh_db.close()


@pytest.mark.asyncio
async def test_roundtrip(populated_db, tmp_path):
    exporter = FullExportService(populated_db)
    export_dir = tmp_path / "export"
    await exporter.export_all(export_dir)

    fresh_db = Database(":memory:")
    await fresh_db.connect()
    await fresh_db.initialize()

    importer = FullImportService(fresh_db)
    result = await importer.import_all(export_dir)

    assert result["projects"] >= 1  # Default project at minimum
    assert result["workflows"] == 1
    assert result["history"] == 1
    assert result["environments"] == 1
    assert result["collections"] == 1

    wf = await fresh_db.fetch_one("SELECT * FROM workflows WHERE id = ?", ("wf-1",))
    assert wf is not None
    assert wf["name"] == "Test Workflow"

    hist = await fresh_db.fetch_one("SELECT * FROM history WHERE id = ?", ("hist-1",))
    assert hist is not None
    assert hist["method"] == "GET"

    env = await fresh_db.fetch_one("SELECT * FROM environments WHERE id = ?", ("env-1",))
    assert env is not None
    assert env["name"] == "Development"

    col = await fresh_db.fetch_one("SELECT * FROM collections WHERE id = ?", ("col-1",))
    assert col is not None
    assert col["name"] == "Test Collection"

    await fresh_db.close()


# ── Workflow document model round-trip tests ───────────────────────────


@pytest.fixture
async def workflow_doc_db(db):
    """DB with a workflow that has layout, sclpll_source, and versions."""
    now = "2026-01-01T00:00:00Z"
    layout = json.dumps({"nodes": {"s1": {"x": 100.0, "y": 200.0}}, "viewport": {"x": 0, "y": 0, "zoom": 1.0}})
    sclpll_source = '@workflow wf-doc "Doc Workflow"\n    A workflow with layout\n\n@step s1\n    request GET https://example.com\n'
    steps = json.dumps([{"id": "s1", "name": "s1", "type": "request", "config": {"inline_request": {"method": "GET", "url": "https://example.com", "headers": {}}}}])
    variables = json.dumps({"base_url": "https://example.com"})

    await db.execute(
        """INSERT INTO workflows (id, name, description, steps, variables, layout, sclpll_source, project_id, revision, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("wf-doc", "Doc Workflow", "A workflow with layout", steps, variables, layout, sclpll_source, DEFAULT_PROJECT_ID, 3, now, now),
    )
    # Save two versions
    await db.execute(
        """INSERT INTO workflow_versions (id, workflow_id, version, sclpll_source, json_source, metadata, author, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("ver-1", "wf-doc", 1, sclpll_source, json.dumps({"id": "wf-doc", "name": "Doc Workflow", "steps": [], "variables": {}}), json.dumps({"_description": "initial"}), "tester", now),
    )
    await db.execute(
        """INSERT INTO workflow_versions (id, workflow_id, version, sclpll_source, json_source, metadata, author, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("ver-2", "wf-doc", 2, sclpll_source, json.dumps({"id": "wf-doc", "name": "Doc Workflow", "steps": [{"id": "s1"}], "variables": {}}), json.dumps({"_description": "added step"}), "tester", now),
    )
    await db.commit()
    return db


@pytest.mark.asyncio
async def test_export_preserves_workflow_document_fields(workflow_doc_db, tmp_path):
    """Export includes layout, sclpll_source, and revision in the JSON file."""
    exporter = FullExportService(workflow_doc_db)
    await exporter.export_all(tmp_path / "export")

    wf_json = tmp_path / "export" / "workflows" / "Doc Workflow.json"
    assert wf_json.exists()
    data = json.loads(wf_json.read_text(encoding="utf-8"))

    assert data["sclpll_source"] != ""
    assert "@workflow" in data["sclpll_source"]
    assert data["layout"]["nodes"]["s1"]["x"] == 100.0
    assert data["revision"] == 3

    # SCLPLL file should also exist
    sclpll_file = tmp_path / "export" / "workflows" / "Doc Workflow.sclpll"
    assert sclpll_file.exists()
    assert "@workflow" in sclpll_file.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_export_preserves_workflow_versions(workflow_doc_db, tmp_path):
    """Export includes a _versions.json file with all version snapshots."""
    exporter = FullExportService(workflow_doc_db)
    await exporter.export_all(tmp_path / "export")

    versions_file = tmp_path / "export" / "workflows" / "_versions.json"
    assert versions_file.exists()
    versions = json.loads(versions_file.read_text(encoding="utf-8"))
    assert len(versions) == 2

    ver1 = next(v for v in versions if v["version"] == 1)
    ver2 = next(v for v in versions if v["version"] == 2)
    assert ver1["workflow_id"] == "wf-doc"
    assert ver2["workflow_id"] == "wf-doc"


@pytest.mark.asyncio
async def test_import_preserves_workflow_document_fields(workflow_doc_db, tmp_path):
    """Import restores layout, sclpll_source, and all workflow fields."""
    exporter = FullExportService(workflow_doc_db)
    export_dir = tmp_path / "export"
    await exporter.export_all(export_dir)

    fresh_db = Database(":memory:")
    await fresh_db.connect()
    await fresh_db.initialize()

    importer = FullImportService(fresh_db)
    result = await importer.import_workflows(export_dir)
    assert result == 1

    wf = await fresh_db.fetch_one("SELECT * FROM workflows WHERE id = ?", ("wf-doc",))
    assert wf is not None
    assert wf["name"] == "Doc Workflow"
    assert wf["sclpll_source"] != ""
    assert "@workflow" in wf["sclpll_source"]

    layout = json.loads(wf["layout"])
    assert layout["nodes"]["s1"]["x"] == 100.0
    assert layout["viewport"]["zoom"] == 1.0

    await fresh_db.close()


@pytest.mark.asyncio
async def test_import_preserves_workflow_versions(workflow_doc_db, tmp_path):
    """Import restores all workflow version snapshots."""
    exporter = FullExportService(workflow_doc_db)
    export_dir = tmp_path / "export"
    await exporter.export_all(export_dir)

    fresh_db = Database(":memory:")
    await fresh_db.connect()
    await fresh_db.initialize()

    importer = FullImportService(fresh_db)
    await importer.import_workflows(export_dir)

    versions = await fresh_db.fetch_all(
        "SELECT * FROM workflow_versions WHERE workflow_id = ? ORDER BY version",
        ("wf-doc",),
    )
    assert len(versions) == 2
    assert versions[0]["version"] == 1
    assert versions[1]["version"] == 2
    assert versions[0]["sclpll_source"] != ""

    await fresh_db.close()


@pytest.mark.asyncio
async def test_import_old_format_workflow_without_layout(tmp_path):
    """Importing an old-format export (no layout/sclpll_source) still works."""
    old_export = tmp_path / "old_export"
    old_export.mkdir(parents=True, exist_ok=True)
    (old_export / "manifest.json").write_text(json.dumps({
        "format": "sclplapi-full-export",
        "version": 1,
        "created_at": "2025-01-01T00:00:00Z",
        "export_id": "old-export-1",
        "sections": ["workflows"],
    }), encoding="utf-8")

    wf_dir = old_export / "workflows"
    wf_dir.mkdir(parents=True)
    # Old format: no layout or sclpll_source fields
    wf_data = {
        "id": "old-wf",
        "name": "Old Workflow",
        "description": "From old export",
        "steps": [{"id": "s1", "name": "s1", "type": "request", "config": {}}],
        "variables": {},
    }
    (wf_dir / "Old Workflow.json").write_text(json.dumps(wf_data), encoding="utf-8")

    fresh_db = Database(":memory:")
    await fresh_db.connect()
    await fresh_db.initialize()

    importer = FullImportService(fresh_db)
    count = await importer.import_workflows(old_export)
    assert count == 1

    wf = await fresh_db.fetch_one("SELECT * FROM workflows WHERE id = ?", ("old-wf",))
    assert wf is not None
    assert wf["name"] == "Old Workflow"
    # layout defaults to empty JSON object
    layout = json.loads(wf["layout"])
    assert layout == {}
    # sclpll_source defaults to empty string
    assert wf["sclpll_source"] == ""

    await fresh_db.close()


@pytest.mark.asyncio
async def test_full_roundtrip_with_document_model(workflow_doc_db, tmp_path):
    """Full export -> import round-trip preserves all workflow document data."""
    exporter = FullExportService(workflow_doc_db)
    export_dir = tmp_path / "export"
    await exporter.export_all(export_dir)

    fresh_db = Database(":memory:")
    await fresh_db.connect()
    await fresh_db.initialize()

    importer = FullImportService(fresh_db)
    result = await importer.import_all(export_dir)

    assert result["workflows"] == 1

    # Verify workflow fields
    wf = await fresh_db.fetch_one("SELECT * FROM workflows WHERE id = ?", ("wf-doc",))
    assert wf is not None
    assert wf["name"] == "Doc Workflow"
    assert wf["revision"] == 3
    assert "@workflow" in wf["sclpll_source"]
    layout = json.loads(wf["layout"])
    assert layout["nodes"]["s1"]["x"] == 100.0

    # Verify versions
    versions = await fresh_db.fetch_all(
        "SELECT * FROM workflow_versions WHERE workflow_id = ? ORDER BY version",
        ("wf-doc",),
    )
    assert len(versions) == 2
    assert versions[0]["version"] == 1
    assert versions[1]["version"] == 2

    await fresh_db.close()
