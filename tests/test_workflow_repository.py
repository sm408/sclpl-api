"""Integration tests for WorkflowRepository.

Covers: CRUD, versioning (save/compare/restore), revision conflicts,
SCLPLL parse/preview/apply, preflight validation, and export/import
preservation of workflow/version data.
"""

from __future__ import annotations

import pytest

from app.core.models.project import DEFAULT_PROJECT_ID
from app.core.models.workflow_document import (
    GraphLayout,
    RevisionConflict,
    WorkflowDocument,
)
from app.services.workflow_service import WorkflowRepository
from app.storage.db import Database

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
async def db(tmp_path):
    """Create and initialize a fresh test database."""
    db_path = str(tmp_path / "test.db")
    database = Database(db_path)
    await database.connect()
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
async def repo(db):
    """Create a WorkflowRepository backed by the test database."""
    return WorkflowRepository(db)


PID = DEFAULT_PROJECT_ID


# ═══════════════════════════════════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════════════════════════════════


class TestWorkflowCRUD:

    async def test_create_workflow(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test Workflow", project_id=PID)
        assert doc.name == "Test Workflow"
        assert doc.project_id == PID
        assert doc.id
        assert doc.revision == 1
        assert doc.created_at is not None

    async def test_create_with_definition(self, repo: WorkflowRepository):
        definition = {
            "id": "custom",
            "name": "Custom",
            "description": "A custom workflow",
            "steps": [{"id": "s1", "name": "s1", "type": "request", "config": {}}],
            "variables": {"base_url": "https://api.example.com"},
        }
        doc = await repo.create(
            name="Custom",
            project_id=PID,
            definition=definition,
        )
        assert doc.definition["steps"][0]["id"] == "s1"
        assert doc.definition["variables"]["base_url"] == "https://api.example.com"

    async def test_create_with_layout(self, repo: WorkflowRepository):
        layout = GraphLayout(
            nodes={"s1": {"x": 100.0, "y": 200.0}},
            viewport={"x": 0.0, "y": 0.0, "zoom": 1.0},
        )
        doc = await repo.create(name="Layout Test", project_id=PID, layout=layout)
        assert doc.layout.nodes["s1"]["x"] == 100.0
        assert doc.layout.viewport["zoom"] == 1.0

    async def test_create_with_sclpll_source(self, repo: WorkflowRepository):
        source = '@workflow wf1 "Test"\n@step s1\n    request GET https://example.com\n'
        doc = await repo.create(
            name="SCLPLL Test", project_id=PID, sclpll_source=source,
        )
        assert doc.sclpll_source == source

    async def test_list_all_empty(self, repo: WorkflowRepository):
        docs = await repo.list_all(project_id=PID)
        assert docs == []

    async def test_list_all(self, repo: WorkflowRepository):
        await repo.create(name="Alpha", project_id=PID)
        await repo.create(name="Beta", project_id=PID)
        docs = await repo.list_all(project_id=PID)
        assert len(docs) == 2
        names = [d.name for d in docs]
        assert "Alpha" in names
        assert "Beta" in names

    async def test_get_existing(self, repo: WorkflowRepository):
        created = await repo.create(name="Fetch Me", project_id=PID)
        fetched = await repo.get(created.id)
        assert fetched is not None
        assert fetched.name == "Fetch Me"
        assert fetched.id == created.id

    async def test_get_nonexistent(self, repo: WorkflowRepository):
        result = await repo.get("nonexistent-id")
        assert result is None

    async def test_update_name(self, repo: WorkflowRepository):
        doc = await repo.create(name="Old Name", project_id=PID)
        updated = await repo.update(doc.id, {"name": "New Name"})
        assert updated is not None
        assert updated.name == "New Name"
        assert updated.revision == 2

    async def test_update_definition(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        new_def = {
            "id": doc.id,
            "name": "Test",
            "description": "",
            "steps": [{"id": "s1", "name": "s1", "type": "request", "config": {}}],
            "variables": {},
        }
        updated = await repo.update(doc.id, {"definition": new_def})
        assert updated is not None
        assert len(updated.definition["steps"]) == 1

    async def test_update_layout(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        layout = GraphLayout(nodes={"s1": {"x": 50.0, "y": 50.0}})
        updated = await repo.update(doc.id, {"layout": layout})
        assert updated is not None
        assert updated.layout.nodes["s1"]["x"] == 50.0

    async def test_update_not_found(self, repo: WorkflowRepository):
        result = await repo.update("nonexistent", {"name": "X"})
        assert result is None

    async def test_update_bumps_revision(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        assert doc.revision == 1
        updated = await repo.update(doc.id, {"name": "Updated"})
        assert updated.revision == 2
        updated2 = await repo.update(doc.id, {"name": "Updated Again"})
        assert updated2.revision == 3

    async def test_delete_existing(self, repo: WorkflowRepository):
        doc = await repo.create(name="Delete Me", project_id=PID)
        success = await repo.delete(doc.id)
        assert success is True
        assert await repo.get(doc.id) is None

    async def test_delete_nonexistent(self, repo: WorkflowRepository):
        success = await repo.delete("nonexistent")
        assert success is False

    async def test_duplicate(self, repo: WorkflowRepository):
        doc = await repo.create(
            name="Original",
            project_id=PID,
            description="Original description",
            sclpll_source="@workflow original\n",
        )
        dup = await repo.duplicate(doc.id)
        assert dup is not None
        assert dup.name == "Original (copy)"
        assert dup.id != doc.id
        assert dup.description == "Original description"
        assert dup.sclpll_source == "@workflow original\n"

    async def test_duplicate_with_custom_name(self, repo: WorkflowRepository):
        doc = await repo.create(name="Original", project_id=PID)
        dup = await repo.duplicate(doc.id, new_name="Custom Copy")
        assert dup is not None
        assert dup.name == "Custom Copy"

    async def test_duplicate_nonexistent(self, repo: WorkflowRepository):
        result = await repo.duplicate("nonexistent")
        assert result is None


# ═══════════════════════════════════════════════════════════════════════
# Versions
# ═══════════════════════════════════════════════════════════════════════


class TestWorkflowVersions:

    async def test_save_version(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        ver = await repo.save_version(doc.id, description="v1", author="tester")
        assert ver is not None
        assert ver.version == 1
        assert ver.description == "v1"
        assert ver.author == "tester"
        assert ver.workflow_id == doc.id

    async def test_save_multiple_versions(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        await repo.save_version(doc.id, description="v1")
        await repo.update(doc.id, {"name": "Updated"})
        v2 = await repo.save_version(doc.id, description="v2")
        assert v2.version == 2

    async def test_list_versions(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        await repo.save_version(doc.id, description="v1")
        await repo.save_version(doc.id, description="v2")
        versions = await repo.list_versions(doc.id)
        assert len(versions) == 2
        # Newest first
        assert versions[0].version == 2
        assert versions[1].version == 1

    async def test_list_versions_empty(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        versions = await repo.list_versions(doc.id)
        assert versions == []

    async def test_get_version(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        await repo.save_version(doc.id, description="v1")
        ver = await repo.get_version(doc.id, 1)
        assert ver is not None
        assert ver.version == 1

    async def test_get_nonexistent_version(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        ver = await repo.get_version(doc.id, 999)
        assert ver is None

    async def test_version_preserves_definition(self, repo: WorkflowRepository):
        definition = {
            "id": "wf1",
            "name": "Test",
            "description": "",
            "steps": [{"id": "s1", "name": "s1", "type": "request", "config": {}}],
            "variables": {"token": "abc"},
        }
        doc = await repo.create(
            name="Test", project_id=PID, definition=definition,
        )
        ver = await repo.save_version(doc.id)
        assert ver.definition["steps"][0]["id"] == "s1"
        assert ver.definition["variables"]["token"] == "abc"

    async def test_version_preserves_sclpll_source(self, repo: WorkflowRepository):
        source = '@workflow wf1\n@step s1\n    request GET https://example.com\n'
        doc = await repo.create(name="Test", project_id=PID, sclpll_source=source)
        ver = await repo.save_version(doc.id)
        assert ver.sclpll_source == source

    async def test_compare_versions(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        await repo.save_version(doc.id, description="v1")
        await repo.update(doc.id, {"name": "Changed"})
        await repo.save_version(doc.id, description="v2")
        diff = await repo.compare_versions(doc.id, 1, 2)
        assert diff is not None
        assert len(diff) > 0
        # Should detect the name change
        name_changes = [d for d in diff if "name" in d.path]
        assert len(name_changes) >= 1

    async def test_compare_nonexistent_versions(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        diff = await repo.compare_versions(doc.id, 1, 2)
        assert diff is None

    async def test_restore_version(self, repo: WorkflowRepository):
        doc = await repo.create(name="Original", project_id=PID)
        await repo.save_version(doc.id, description="v1 original")
        await repo.update(doc.id, {"name": "Changed"})
        restored = await repo.restore_version(doc.id, 1)
        assert restored is not None
        assert restored.name == "Original"
        # Revision should have bumped
        assert restored.revision > 1

    async def test_restore_creates_auto_save(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        await repo.save_version(doc.id, description="v1")
        await repo.update(doc.id, {"name": "Changed"})
        await repo.restore_version(doc.id, 1)
        versions = await repo.list_versions(doc.id)
        # Should have v1 + auto-save before restore
        assert len(versions) >= 2
        auto_saves = [v for v in versions if "Auto-save" in (v.description or "")]
        assert len(auto_saves) >= 1

    async def test_restore_nonexistent_version(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        result = await repo.restore_version(doc.id, 999)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════
# Revision Conflicts
# ═══════════════════════════════════════════════════════════════════════


class TestRevisionConflicts:

    async def test_update_with_matching_revision(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        result = await repo.update(doc.id, {"name": "Updated"}, revision=1)
        assert isinstance(result, WorkflowDocument)
        assert result.name == "Updated"

    async def test_update_with_stale_revision(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        # Bump revision by changing definition
        new_def = {
            "id": doc.id,
            "name": "Test",
            "description": "",
            "steps": [{"id": "s1", "name": "s1", "type": "request", "config": {}}],
            "variables": {},
        }
        await repo.update(doc.id, {"definition": new_def})
        # Try to update with stale revision
        result = await repo.update(doc.id, {"name": "Conflict"}, revision=1)
        assert isinstance(result, RevisionConflict)
        assert result.current_revision == 2
        assert result.attempted_revision == 1
        assert result.current_definition is not None

    async def test_conflict_includes_current_definition(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        new_def = {
            "id": doc.id,
            "name": "Test",
            "description": "",
            "steps": [{"id": "s1", "name": "s1", "type": "request", "config": {}}],
            "variables": {},
        }
        await repo.update(doc.id, {"definition": new_def})
        result = await repo.update(doc.id, {"name": "Client Change"}, revision=1)
        assert isinstance(result, RevisionConflict)
        # The current definition should reflect the server-side change
        assert len(result.current_definition.get("steps", [])) == 1
        assert result.current_definition["steps"][0]["id"] == "s1"

    async def test_no_conflict_when_revision_none(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        await repo.update(doc.id, {"name": "Changed"})
        # No revision check
        result = await repo.update(doc.id, {"name": "No Conflict"})
        assert isinstance(result, WorkflowDocument)


# ═══════════════════════════════════════════════════════════════════════
# SCLPLL Integration
# ═══════════════════════════════════════════════════════════════════════


class TestSCLPLLIntegration:

    async def test_parse_sclpll_valid(self, repo: WorkflowRepository):
        source = '@workflow wf1 "Test"\n@step s1\n    request GET https://example.com\n'
        result = repo.parse_sclpll(source)
        assert result.success is True
        assert result.definition is not None
        assert result.definition["id"] == "wf1"
        assert result.source_hash

    async def test_parse_sclpll_invalid(self, repo: WorkflowRepository):
        result = repo.parse_sclpll("invalid source")
        assert result.success is False
        assert len(result.errors) >= 1

    async def test_preview_sclpll_no_current(self, repo: WorkflowRepository):
        source = '@workflow wf1\n@step s1\n    request GET https://example.com\n'
        result = repo.preview_sclpll(source)
        assert result.definition is not None
        assert result.sclpll_source
        assert result.losses == []

    async def test_preview_sclpll_with_current(self, repo: WorkflowRepository):
        source = '@workflow wf1\n@step s1\n    request GET https://new.com\n'
        current = {
            "id": "wf1",
            "name": "Test",
            "description": "",
            "steps": [{"id": "s1", "name": "s1", "type": "request", "config": {"inline_request": {"method": "GET", "url": "https://old.com", "headers": {}}}}],
            "variables": {},
        }
        result = repo.preview_sclpll(source, current_definition=current)
        assert len(result.diff) > 0

    async def test_preview_detects_losses(self, repo: WorkflowRepository):
        source = '@workflow wf1\n@step s1\n    request GET https://example.com\n'
        current = {
            "id": "wf1",
            "name": "Test",
            "description": "",
            "steps": [
                {
                    "id": "s1",
                    "name": "s1",
                    "type": "request",
                    "config": {"inline_request": {"method": "GET", "url": "https://example.com", "headers": {}}},
                    "retry": {"max_retries": 3},
                }
            ],
            "variables": {},
        }
        result = repo.preview_sclpll(source, current_definition=current)
        assert len(result.losses) >= 1
        assert "retry" in result.losses[0]

    async def test_preview_sclpll_parse_failure(self, repo: WorkflowRepository):
        with pytest.raises(ValueError, match="SCLPLL parse failed"):
            repo.preview_sclpll("invalid source")

    async def test_apply_sclpll(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        source = f'@workflow {doc.id} "Updated"\n@step s1\n    request GET https://example.com\n'
        result = await repo.apply_sclpll(doc.id, source)
        assert isinstance(result, WorkflowDocument)
        assert len(result.definition["steps"]) == 1
        assert result.sclpll_source

    async def test_apply_sclpll_with_revision(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        source = f'@workflow {doc.id} "Updated"\n@step s1\n    request GET https://example.com\n'
        result = await repo.apply_sclpll(doc.id, source, revision=1)
        assert isinstance(result, WorkflowDocument)

    async def test_apply_sclpll_stale_revision(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        await repo.update(doc.id, {"name": "Changed"})
        source = f'@workflow {doc.id} "Conflict"\n@step s1\n    request GET https://example.com\n'
        result = await repo.apply_sclpll(doc.id, source, revision=1)
        assert isinstance(result, RevisionConflict)

    async def test_apply_sclpll_nonexistent(self, repo: WorkflowRepository):
        result = await repo.apply_sclpll("nonexistent", "@workflow wf1\n")
        assert result is None

    async def test_apply_sclpll_invalid_source(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        with pytest.raises(ValueError, match="SCLPLL parse failed"):
            await repo.apply_sclpll(doc.id, "invalid source")

    async def test_generate_sclpll(self, repo: WorkflowRepository):
        definition = {
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
        }
        source = repo.generate_sclpll(definition)
        assert "@workflow wf1" in source
        assert "request GET https://example.com" in source


# ═══════════════════════════════════════════════════════════════════════
# Preflight Validation
# ═══════════════════════════════════════════════════════════════════════


class TestPreflightValidation:

    async def test_valid_workflow(self, repo: WorkflowRepository):
        definition = {
            "id": "wf1",
            "steps": [
                {"id": "s1", "type": "request", "config": {}},
                {"id": "s2", "type": "request", "config": {}, "depends_on": ["s1"]},
            ],
        }
        result = repo.validate_preflight(definition)
        assert result.valid is True
        assert result.errors == []

    async def test_circular_dependency(self, repo: WorkflowRepository):
        definition = {
            "id": "wf1",
            "steps": [
                {"id": "a", "type": "request", "config": {}, "depends_on": ["b"]},
                {"id": "b", "type": "request", "config": {}, "depends_on": ["a"]},
            ],
        }
        result = repo.validate_preflight(definition)
        assert result.valid is False
        assert any("circular" in e.message.lower() for e in result.errors)

    async def test_broken_dependency(self, repo: WorkflowRepository):
        definition = {
            "id": "wf1",
            "steps": [
                {"id": "s1", "type": "request", "config": {}, "depends_on": ["missing"]},
            ],
        }
        result = repo.validate_preflight(definition)
        assert result.valid is False
        assert any("missing" in e.message for e in result.errors)

    async def test_missing_id_warning(self, repo: WorkflowRepository):
        definition = {"id": "", "steps": []}
        result = repo.validate_preflight(definition)
        assert any("id" in w.message.lower() for w in result.warnings)


# ═══════════════════════════════════════════════════════════════════════
# Definition / Layout Separation
# ═══════════════════════════════════════════════════════════════════════


class TestDefinitionLayoutSeparation:

    async def test_layout_changes_dont_affect_definition(self, repo: WorkflowRepository):
        doc = await repo.create(name="Test", project_id=PID)
        layout = GraphLayout(nodes={"s1": {"x": 999.0, "y": 999.0}})
        updated = await repo.update(doc.id, {"layout": layout})
        # Definition should be unchanged
        assert updated.definition == doc.definition
        # Layout should be updated
        assert updated.layout.nodes["s1"]["x"] == 999.0

    async def test_definition_changes_dont_affect_layout(self, repo: WorkflowRepository):
        layout = GraphLayout(nodes={"s1": {"x": 100.0, "y": 200.0}})
        doc = await repo.create(name="Test", project_id=PID, layout=layout)
        new_def = {
            "id": doc.id,
            "name": "Updated",
            "description": "",
            "steps": [{"id": "s2", "name": "s2", "type": "request", "config": {}}],
            "variables": {},
        }
        updated = await repo.update(doc.id, {"definition": new_def})
        # Layout should be unchanged
        assert updated.layout.nodes["s1"]["x"] == 100.0
        # Definition should be updated
        assert updated.definition["steps"][0]["id"] == "s2"
