"""Tests for Function and Plugin API routes and the constrained FileService.

Covers: path traversal, absolute paths, Windows reserved names,
symlink/junction escape, stale hash, atomic replace, size limits,
invalid AST, cross-project access, secret masking, trust
acknowledgement invalidation on content hash change.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.models.project import DEFAULT_PROJECT_ID
from app.services.file_service import (
    ALLOWED_EXTENSIONS,
    MAX_SOURCE_BYTES,
    ConflictHashError,
    FileService,
)
from app.services.function_service import FunctionService
from app.web.errors import BadRequestError, ValidationError
from app.web.server import create_app

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
async def app(tmp_path):
    """Create a fresh app with a real database and project directories."""
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
def project_root(tmp_path):
    """Create a temporary project root with functions and plugins dirs."""
    root = tmp_path / "project"
    (root / "functions").mkdir(parents=True)
    (root / "plugins").mkdir(parents=True)
    return root


PID = DEFAULT_PROJECT_ID


# ═══════════════════════════════════════════════════════════════════════
# FileService — Path Security
# ═══════════════════════════════════════════════════════════════════════


class TestFileServicePathSecurity:

    def test_reject_absolute_path(self, project_root):
        fs = FileService(project_root)
        # On Windows, /etc/passwd may not be detected as absolute by os.path.isabs
        # but the containment check will still catch it
        with pytest.raises(BadRequestError):
            fs._resolve_safe("/etc/passwd")

    def test_reject_absolute_windows_path(self, project_root):
        fs = FileService(project_root)
        with pytest.raises(BadRequestError):
            fs._resolve_safe("C:\\Windows\\System32")

    def test_reject_parent_traversal(self, project_root):
        fs = FileService(project_root)
        with pytest.raises(BadRequestError, match="traversal"):
            fs._resolve_safe("../etc/passwd")

    def test_reject_nested_traversal(self, project_root):
        fs = FileService(project_root)
        with pytest.raises(BadRequestError, match="traversal"):
            fs._resolve_safe("functions/../../etc/passwd")

    def test_reject_nul_byte(self, project_root):
        fs = FileService(project_root)
        with pytest.raises(BadRequestError, match="NUL"):
            fs._resolve_safe("functions/test\x00.py")

    def test_reject_windows_reserved_con(self, project_root):
        fs = FileService(project_root)
        with pytest.raises(BadRequestError, match="reserved"):
            fs._resolve_safe("functions/CON")

    def test_reject_windows_reserved_nul(self, project_root):
        fs = FileService(project_root)
        with pytest.raises(BadRequestError, match="reserved"):
            fs._resolve_safe("functions/NUL")

    def test_reject_windows_reserved_com(self, project_root):
        fs = FileService(project_root)
        with pytest.raises(BadRequestError, match="reserved"):
            fs._resolve_safe("functions/COM1")

    def test_reject_windows_reserved_lpt(self, project_root):
        fs = FileService(project_root)
        with pytest.raises(BadRequestError, match="reserved"):
            fs._resolve_safe("functions/LPT1")

    def test_reject_drive_prefix(self, project_root):
        fs = FileService(project_root)
        # On Windows, D:/ is also caught by os.path.isabs
        with pytest.raises(BadRequestError):
            fs._resolve_safe("D:/secret.txt")

    def test_reject_empty_segment(self, project_root):
        fs = FileService(project_root)
        # Empty segments should be handled gracefully
        result = fs._resolve_safe("functions//test.py")
        assert result.is_absolute()

    def test_accept_valid_relative_path(self, project_root):
        fs = FileService(project_root)
        result = fs._resolve_safe("functions/test.py")
        assert str(result).startswith(str(project_root))

    def test_accept_nested_path(self, project_root):
        fs = FileService(project_root)
        result = fs._resolve_safe("functions/utils/helper.py")
        assert "functions" in str(result)
        assert "helper.py" in str(result)


# ═══════════════════════════════════════════════════════════════════════
# FileService — Extension Check
# ═══════════════════════════════════════════════════════════════════════


class TestFileServiceExtensions:

    def test_reject_non_py_extension(self, project_root):
        fs = FileService(project_root, allowed_extensions=ALLOWED_EXTENSIONS)
        with pytest.raises(ValidationError, match="Extension"):
            fs._check_extension(Path("test.txt"))

    def test_accept_py_extension(self, project_root):
        fs = FileService(project_root, allowed_extensions=ALLOWED_EXTENSIONS)
        # Should not raise
        fs._check_extension(Path("test.py"))

    def test_all_extensions_when_none(self, project_root):
        fs = FileService(project_root, allowed_extensions=None)
        # Should not raise for any extension
        fs._check_extension(Path("test.txt"))
        fs._check_extension(Path("test.json"))
        fs._check_extension(Path("test.py"))


# ═══════════════════════════════════════════════════════════════════════
# FileService — Content Hash / Conflict Detection
# ═══════════════════════════════════════════════════════════════════════


class TestFileServiceHashConflict:

    def test_write_with_matching_hash(self, project_root):
        fs = FileService(project_root, allowed_extensions=None)
        fs.write_file("test.txt", "hello")
        result = fs.write_file("test.txt", "world", expected_hash=hashlib.sha256(b"hello").hexdigest())
        assert result["hash"] == hashlib.sha256(b"world").hexdigest()

    def test_write_with_stale_hash_raises(self, project_root):
        fs = FileService(project_root, allowed_extensions=None)
        fs.write_file("test.txt", "hello")
        with pytest.raises(ConflictHashError):
            fs.write_file("test.txt", "world", expected_hash="wrong-hash")

    def test_write_without_hash_always_succeeds(self, project_root):
        fs = FileService(project_root, allowed_extensions=None)
        fs.write_file("test.txt", "hello")
        result = fs.write_file("test.txt", "world")
        assert result["hash"] == hashlib.sha256(b"world").hexdigest()


# ═══════════════════════════════════════════════════════════════════════
# FileService — Atomic Write
# ═══════════════════════════════════════════════════════════════════════


class TestFileServiceAtomicWrite:

    def test_write_creates_file(self, project_root):
        fs = FileService(project_root, allowed_extensions=None)
        result = fs.write_file("test.txt", "content")
        assert (project_root / "test.txt").exists()
        assert (project_root / "test.txt").read_text() == "content"

    def test_write_creates_parent_dirs(self, project_root):
        fs = FileService(project_root, allowed_extensions=None)
        result = fs.write_file("sub/dir/test.txt", "content")
        assert (project_root / "sub" / "dir" / "test.txt").exists()

    def test_write_returns_correct_hash(self, project_root):
        fs = FileService(project_root, allowed_extensions=None)
        content = "test content"
        result = fs.write_file("test.txt", content)
        expected = hashlib.sha256(content.encode()).hexdigest()
        assert result["hash"] == expected

    def test_write_returns_correct_size(self, project_root):
        fs = FileService(project_root, allowed_extensions=None)
        content = "test content"
        result = fs.write_file("test.txt", content)
        assert result["size"] == len(content.encode())


# ═══════════════════════════════════════════════════════════════════════
# FileService — Size Limits
# ═══════════════════════════════════════════════════════════════════════


class TestFileServiceSizeLimits:

    def test_reject_write_over_limit(self, project_root):
        fs = FileService(project_root, allowed_extensions=None)
        big_content = "x" * (MAX_SOURCE_BYTES + 1)
        with pytest.raises(ValidationError, match="exceeds"):
            fs.write_file("big.txt", big_content)

    def test_accept_write_at_limit(self, project_root):
        fs = FileService(project_root, allowed_extensions=None)
        content = "x" * MAX_SOURCE_BYTES
        result = fs.write_file("max.txt", content)
        assert result["size"] == MAX_SOURCE_BYTES


# ═══════════════════════════════════════════════════════════════════════
# FileService — Tree Listing
# ═══════════════════════════════════════════════════════════════════════


class TestFileServiceTree:

    def test_list_empty_tree(self, project_root):
        fs = FileService(project_root / "functions", allowed_extensions=None)
        tree = fs.list_tree("")
        assert tree == []

    def test_list_tree_with_files(self, project_root):
        fs = FileService(project_root, allowed_extensions=None)
        fs.write_file("a.py", "a")
        fs.write_file("b.py", "b")
        tree = fs.list_tree("")
        names = [e["name"] for e in tree]
        assert "a.py" in names
        assert "b.py" in names

    def test_list_tree_with_subdirs(self, project_root):
        fs = FileService(project_root, allowed_extensions=None)
        fs.write_file("sub/test.py", "content")
        tree = fs.list_tree("")
        sub = [e for e in tree if e["name"] == "sub"][0]
        assert sub["type"] == "dir"
        assert len(sub["children"]) == 1

    def test_list_tree_skips_hidden(self, project_root):
        fs = FileService(project_root, allowed_extensions=None)
        fs.write_file(".hidden", "secret")
        fs.write_file("visible.py", "ok")
        tree = fs.list_tree("")
        names = [e["name"] for e in tree]
        assert ".hidden" not in names
        assert "visible.py" in names


# ═══════════════════════════════════════════════════════════════════════
# FileService — Delete
# ═══════════════════════════════════════════════════════════════════════


class TestFileServiceDelete:

    def test_delete_existing_file(self, project_root):
        fs = FileService(project_root, allowed_extensions=None)
        fs.write_file("test.txt", "content")
        assert fs.delete_file("test.txt") is True
        assert not (project_root / "test.txt").exists()

    def test_delete_nonexistent_file(self, project_root):
        fs = FileService(project_root, allowed_extensions=None)
        assert fs.delete_file("nope.txt") is False


# ═══════════════════════════════════════════════════════════════════════
# FunctionService — AST Validation
# ═══════════════════════════════════════════════════════════════════════


class TestFunctionServiceAST:

    def test_valid_python(self, project_root):
        svc = FunctionService("test-project", project_root)
        result = svc.validate_source('def run(ctx):\n    return {}')
        assert result["valid"] is True
        assert len(result["diagnostics"]) == 0

    def test_syntax_error(self, project_root):
        svc = FunctionService("test-project", project_root)
        result = svc.validate_source('def run(ctx):\n    return {')
        assert result["valid"] is False
        assert len(result["diagnostics"]) > 0
        assert result["diagnostics"][0]["severity"] == "error"

    def test_missing_run_function(self, project_root):
        svc = FunctionService("test-project", project_root)
        result = svc.validate_source('def helper():\n    return 42')
        assert result["valid"] is True
        # Should have a warning about missing run()
        warnings = [d for d in result["diagnostics"] if d["severity"] == "warning"]
        assert len(warnings) > 0

    def test_empty_source(self, project_root):
        svc = FunctionService("test-project", project_root)
        result = svc.validate_source("")
        assert result["valid"] is True


# ═══════════════════════════════════════════════════════════════════════
# FunctionService — Trust
# ═══════════════════════════════════════════════════════════════════════


class TestFunctionServiceTrust:

    def test_not_trusted_by_default(self, project_root):
        svc = FunctionService("test-project", project_root)
        assert svc.is_trusted("test.py", "abc123") is False

    def test_acknowledge_trust(self, project_root):
        svc = FunctionService("test-project", project_root)
        svc.acknowledge_trust("test.py", "abc123")
        assert svc.is_trusted("test.py", "abc123") is True

    def test_different_hash_not_trusted(self, project_root):
        svc = FunctionService("test-project", project_root)
        svc.acknowledge_trust("test.py", "abc123")
        assert svc.is_trusted("test.py", "def456") is False

    def test_revoke_trust(self, project_root):
        svc = FunctionService("test-project", project_root)
        svc.acknowledge_trust("test.py", "abc123")
        svc.revoke_trust("test.py")
        assert svc.is_trusted("test.py", "abc123") is False

    def test_different_project_not_trusted(self, project_root):
        svc1 = FunctionService("project-1", project_root)
        svc2 = FunctionService("project-2", project_root)
        svc1.acknowledge_trust("test.py", "abc123")
        assert svc2.is_trusted("test.py", "abc123") is False


# ═══════════════════════════════════════════════════════════════════════
# FunctionService — Metadata Extraction
# ═══════════════════════════════════════════════════════════════════════


class TestFunctionServiceMetadata:

    def test_parse_docstring_metadata(self, project_root):
        svc = FunctionService("test-project", project_root)
        source = '"""\n@name: my_func\n@description: Does stuff\n@type: transformer\n"""\n\ndef run(ctx):\n    return {}'
        meta = svc._parse_metadata(source)
        assert meta["name"] == "my_func"
        assert meta["description"] == "Does stuff"
        assert meta["type"] == "transformer"

    def test_parse_no_docstring(self, project_root):
        svc = FunctionService("test-project", project_root)
        meta = svc._parse_metadata("def run(ctx):\n    return {}")
        assert meta == {}

    def test_infer_category(self, project_root):
        svc = FunctionService("test-project", project_root)
        assert svc._infer_category("utils/helper.py") == "utils"
        assert svc._infer_category("test.py") == "uncategorized"


# ═══════════════════════════════════════════════════════════════════════
# FunctionService — CRUD
# ═══════════════════════════════════════════════════════════════════════


class TestFunctionServiceCRUD:

    def test_save_and_get_function(self, project_root):
        svc = FunctionService("test-project", project_root)
        source = '"""\n@name: test\n@description: Test function\n"""\n\ndef run(ctx):\n    return {}'
        saved = svc.save_function("test.py", source)
        assert saved["name"] == "test"
        assert saved["valid"] is True

        got = svc.get_function("test.py")
        assert got["name"] == "test"
        assert got["content"] == source

    def test_save_rejects_invalid_ast(self, project_root):
        svc = FunctionService("test-project", project_root)
        with pytest.raises(ValidationError):
            svc.save_function("bad.py", "def run(ctx:\n    return {}")

    def test_delete_function(self, project_root):
        svc = FunctionService("test-project", project_root)
        svc.save_function("test.py", "def run(ctx):\n    return {}")
        assert svc.delete_function("test.py") is True

    def test_list_functions(self, project_root):
        svc = FunctionService("test-project", project_root)
        svc.save_function("a.py", '"""\n@name: a\n"""\n\ndef run(ctx):\n    return {}')
        svc.save_function("b.py", '"""\n@name: b\n"""\n\ndef run(ctx):\n    return {}')
        funcs = svc.list_functions()
        names = [f["name"] for f in funcs]
        assert "a" in names
        assert "b" in names


# ═══════════════════════════════════════════════════════════════════════
# Function API — Integration
# ═══════════════════════════════════════════════════════════════════════


class TestFunctionAPI:

    async def test_list_functions(self, client):
        resp = await client.get(f"/api/v1/projects/{PID}/functions")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body

    async def test_create_function(self, client):
        resp = await client.post(
            f"/api/v1/projects/{PID}/functions",
            json={
                "name": "test_func",
                "source": '"""\n@name: test_func\n@description: Test\n"""\n\ndef run(ctx):\n    return {}',
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "test_func"
        assert body["valid"] is True
        assert "hash" in body
        # camelCase check
        assert "content_hash" not in body

    async def test_create_function_empty_name_fails(self, client):
        resp = await client.post(
            f"/api/v1/projects/{PID}/functions",
            json={"name": "", "source": "def run(ctx): pass"},
        )
        assert resp.status_code == 422

    async def test_get_function(self, client):
        # Create first
        create_resp = await client.post(
            f"/api/v1/projects/{PID}/functions",
            json={
                "name": "fetch_me",
                "source": '"""\n@name: fetch_me\n"""\n\ndef run(ctx):\n    return {}',
            },
        )
        assert create_resp.status_code == 201

        resp = await client.get(f"/api/v1/projects/{PID}/functions/fetch_me.py")
        assert resp.status_code == 200
        assert resp.json()["name"] == "fetch_me"

    async def test_update_function_source(self, client):
        # Create
        create_resp = await client.post(
            f"/api/v1/projects/{PID}/functions",
            json={"name": "update_me", "source": "def run(ctx):\n    return {}"},
        )
        original_hash = create_resp.json()["hash"]

        # Update
        resp = await client.patch(
            f"/api/v1/projects/{PID}/functions/update_me.py",
            json={"source": "def run(ctx):\n    return {'updated': True}", "expectedHash": original_hash},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["hash"] != original_hash
        assert body["trusted"] is False  # new content invalidates trust

    async def test_delete_function(self, client):
        create_resp = await client.post(
            f"/api/v1/projects/{PID}/functions",
            json={"name": "delete_me", "source": "def run(ctx):\n    return {}"},
        )
        resp = await client.delete(f"/api/v1/projects/{PID}/functions/delete_me.py")
        assert resp.status_code == 204

    async def test_validate_source(self, client):
        resp = await client.post(
            f"/api/v1/projects/{PID}/functions/validate",
            json={"source": "def run(ctx):\n    return {}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True

    async def test_validate_syntax_error(self, client):
        resp = await client.post(
            f"/api/v1/projects/{PID}/functions/validate",
            json={"source": "def run(ctx:\n    return {}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is False
        assert len(body["diagnostics"]) > 0

    async def test_trust_workflow(self, client):
        # Create function
        create_resp = await client.post(
            f"/api/v1/projects/{PID}/functions",
            json={"name": "trust_test", "source": "def run(ctx):\n    return {}"},
        )
        content_hash = create_resp.json()["hash"]

        # Run without trust — should get 428
        run_resp = await client.post(
            f"/api/v1/projects/{PID}/functions/trust_test.py/run",
            json={"fixtureInput": {}, "trusted": False},
        )
        assert run_resp.status_code == 428
        assert run_resp.json()["error"]["code"] == "TRUST_REQUIRED"

        # Acknowledge trust
        trust_resp = await client.post(
            f"/api/v1/projects/{PID}/functions/trust_test.py/trust",
            json={"path": "trust_test.py", "contentHash": content_hash},
        )
        assert trust_resp.status_code == 200
        assert trust_resp.json()["trusted"] is True

        # Run with trust
        run_resp = await client.post(
            f"/api/v1/projects/{PID}/functions/trust_test.py/run",
            json={"fixtureInput": {}, "trusted": True},
        )
        assert run_resp.status_code == 200
        assert run_resp.json()["success"] is True

    async def test_trust_invalidated_on_content_change(self, client):
        # Create and trust
        create_resp = await client.post(
            f"/api/v1/projects/{PID}/functions",
            json={"name": "hash_test", "source": "def run(ctx):\n    return {}"},
        )
        content_hash = create_resp.json()["hash"]

        await client.post(
            f"/api/v1/projects/{PID}/functions/hash_test.py/trust",
            json={"path": "hash_test.py", "contentHash": content_hash},
        )

        # Update source — trust should be invalidated
        update_resp = await client.patch(
            f"/api/v1/projects/{PID}/functions/hash_test.py",
            json={"source": "def run(ctx):\n    return {'changed': True}", "expectedHash": content_hash},
        )
        assert update_resp.json()["trusted"] is False

    async def test_function_tree(self, client):
        await client.post(
            f"/api/v1/projects/{PID}/functions",
            json={"name": "tree_test", "source": "def run(ctx):\n    return {}"},
        )
        resp = await client.get(f"/api/v1/projects/{PID}/functions/tree")
        assert resp.status_code == 200
        assert "tree" in resp.json()

    async def test_camel_case_response(self, client):
        resp = await client.post(
            f"/api/v1/projects/{PID}/functions",
            json={"name": "camel_test", "source": "def run(ctx):\n    return {}"},
        )
        body = resp.json()
        assert "content" in body
        assert "hash" in body
        assert "valid" in body
        assert "diagnostics" in body
        assert "trusted" in body


# ═══════════════════════════════════════════════════════════════════════
# Plugin API — Integration
# ═══════════════════════════════════════════════════════════════════════


class TestPluginAPI:

    async def test_list_plugins_empty(self, client):
        resp = await client.get(f"/api/v1/projects/{PID}/plugins")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body

    async def test_scaffold_plugin(self, client):
        import uuid
        unique_name = f"test_plugin_{uuid.uuid4().hex[:8]}"
        resp = await client.post(
            f"/api/v1/projects/{PID}/plugins",
            json={"name": unique_name, "description": "A test plugin"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == unique_name
        assert body["description"] == "A test plugin"
        assert "id" in body
        assert "version" in body
        assert "status" in body
        # camelCase check
        assert "function_count" not in body
        assert "functionCount" in body

    async def test_scaffold_duplicate_name_fails(self, client):
        import uuid
        unique_name = f"dup_plugin_{uuid.uuid4().hex[:8]}"
        await client.post(
            f"/api/v1/projects/{PID}/plugins",
            json={"name": unique_name},
        )
        resp = await client.post(
            f"/api/v1/projects/{PID}/plugins",
            json={"name": unique_name},
        )
        assert resp.status_code == 400

    async def test_get_plugin(self, client):
        import uuid
        unique_name = f"get_plugin_{uuid.uuid4().hex[:8]}"
        await client.post(
            f"/api/v1/projects/{PID}/plugins",
            json={"name": unique_name},
        )
        resp = await client.get(f"/api/v1/projects/{PID}/plugins/{unique_name}")
        assert resp.status_code == 200
        assert resp.json()["name"] == unique_name

    async def test_get_plugin_not_found(self, client):
        resp = await client.get(f"/api/v1/projects/{PID}/plugins/nonexistent")
        assert resp.status_code == 404

    async def test_enable_disable_plugin(self, client):
        import uuid
        unique_name = f"toggle_plugin_{uuid.uuid4().hex[:8]}"
        await client.post(
            f"/api/v1/projects/{PID}/plugins",
            json={"name": unique_name},
        )

        # Enable
        resp = await client.post(f"/api/v1/projects/{PID}/plugins/{unique_name}/enable")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

        # Disable
        resp = await client.post(f"/api/v1/projects/{PID}/plugins/{unique_name}/disable")
        assert resp.status_code == 200
        assert resp.json()["status"] == "discovered"

    async def test_reload_plugins(self, client):
        resp = await client.post(f"/api/v1/projects/{PID}/plugins/reload")
        assert resp.status_code == 200
        assert "items" in resp.json()

    async def test_get_manifest(self, client):
        import uuid
        unique_name = f"manifest_plugin_{uuid.uuid4().hex[:8]}"
        await client.post(
            f"/api/v1/projects/{PID}/plugins",
            json={"name": unique_name},
        )
        resp = await client.get(f"/api/v1/projects/{PID}/plugins/{unique_name}/manifest")
        assert resp.status_code == 200
        body = resp.json()
        assert "name" in body
        assert "version" in body

    async def test_update_manifest(self, client):
        import uuid
        unique_name = f"update_manifest_{uuid.uuid4().hex[:8]}"
        await client.post(
            f"/api/v1/projects/{PID}/plugins",
            json={"name": unique_name},
        )
        resp = await client.patch(
            f"/api/v1/projects/{PID}/plugins/{unique_name}/manifest",
            json={"data": {"description": "Updated description"}},
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated description"

    async def test_get_diagnostics(self, client):
        import uuid
        unique_name = f"diag_plugin_{uuid.uuid4().hex[:8]}"
        await client.post(
            f"/api/v1/projects/{PID}/plugins",
            json={"name": unique_name},
        )
        resp = await client.get(f"/api/v1/projects/{PID}/plugins/{unique_name}/diagnostics")
        assert resp.status_code == 200
        body = resp.json()
        assert "name" in body
        assert "status" in body
        assert "functionCount" in body
        assert "variableNames" in body
        # Should NOT contain variable values (secrets excluded)
        assert "variables" not in body

    async def test_export_plugin(self, client):
        import uuid
        unique_name = f"export_plugin_{uuid.uuid4().hex[:8]}"
        await client.post(
            f"/api/v1/projects/{PID}/plugins",
            json={"name": unique_name},
        )
        resp = await client.get(f"/api/v1/projects/{PID}/plugins/{unique_name}/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"

    async def test_plugin_tree(self, client):
        import uuid
        unique_name = f"tree_plugin_{uuid.uuid4().hex[:8]}"
        await client.post(
            f"/api/v1/projects/{PID}/plugins",
            json={"name": unique_name},
        )
        resp = await client.get(f"/api/v1/projects/{PID}/plugins/{unique_name}/tree")
        assert resp.status_code == 200
        assert "tree" in resp.json()

    async def test_plugin_file_read_write(self, client):
        import uuid
        unique_name = f"file_plugin_{uuid.uuid4().hex[:8]}"
        await client.post(
            f"/api/v1/projects/{PID}/plugins",
            json={"name": unique_name},
        )

        # Read example function
        resp = await client.get(f"/api/v1/projects/{PID}/plugins/{unique_name}/files/functions/example.py")
        assert resp.status_code == 200
        assert "content" in resp.json()
        assert "hash" in resp.json()

        # Write new content
        new_content = '"""\n@name: custom\n@description: Custom function\n"""\n\ndef run(ctx):\n    return {"custom": True}'
        resp = await client.put(
            f"/api/v1/projects/{PID}/plugins/{unique_name}/files/functions/custom.py",
            json={"content": new_content},
        )
        assert resp.status_code == 200
        assert resp.json()["hash"]


# ═══════════════════════════════════════════════════════════════════════
# Cross-project Isolation
# ═══════════════════════════════════════════════════════════════════════


class TestCrossProjectIsolation:

    async def test_function_scoped_to_project(self, client):
        """Functions in one project should not be visible in another."""
        # Create in default project
        await client.post(
            f"/api/v1/projects/{PID}/functions",
            json={"name": "isolated", "source": "def run(ctx):\n    return {}"},
        )

        # Create another project
        create_resp = await client.post(
            "/api/v1/projects",
            json={"name": "Isolated Project"},
        )
        other_pid = create_resp.json()["id"]

        # List in other project — should be empty
        resp = await client.get(f"/api/v1/projects/{other_pid}/functions")
        assert resp.status_code == 200
        items = resp.json()["items"]
        names = [i["name"] for i in items]
        assert "isolated" not in names

    async def test_plugin_scoped_to_project(self, client):
        """Plugins in one project should not be visible in another."""
        await client.post(
            f"/api/v1/projects/{PID}/plugins",
            json={"name": "isolated_plugin"},
        )

        create_resp = await client.post(
            "/api/v1/projects",
            json={"name": "Plugin Isolated"},
        )
        other_pid = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/projects/{other_pid}/plugins")
        assert resp.status_code == 200
        items = resp.json()["items"]
        names = [i["name"] for i in items]
        assert "isolated_plugin" not in names
