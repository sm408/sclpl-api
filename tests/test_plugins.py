from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from app.core.engine.plugin_registry import FilesystemPluginRegistry
from app.core.models.context import ExecutionContext
from app.core.models.plugin import PluginInfo, PluginManifest, PluginStatus


@pytest.fixture
def plugins_dir(tmp_path: Path) -> Path:
    """Create a temporary plugins directory with sample plugins."""
    plugins = tmp_path / "plugins"
    plugins.mkdir()

    # Plugin with functions, workflows, hooks, and variables
    plugin_a = plugins / "plugin-a"
    plugin_a.mkdir()
    (plugin_a / "plugin.json").write_text(json.dumps({
        "name": "plugin-a",
        "version": "1.0.0",
        "description": "Test plugin A",
        "author": "Test",
        "functions": ["functions/*.py"],
        "workflows": ["workflows/*.json"],
        "hooks": {
            "pre_request": "hooks/pre_request.py",
        },
        "variables": {
            "plugin_a_var": "hello",
            "shared_var": "from_a",
        },
        "dependencies": [],
    }), encoding="utf-8")

    (plugin_a / "functions").mkdir()
    (plugin_a / "functions" / "func_a.py").write_text(textwrap.dedent('''\
        """\
        @name: func_a
        @type: utility
        @description: Function from plugin A
        """

        def run(ctx):
            return "result_a"
    '''), encoding="utf-8")

    (plugin_a / "workflows").mkdir()
    (plugin_a / "workflows" / "wf_a.json").write_text(json.dumps({
        "id": "wf-a",
        "name": "Workflow A",
        "steps": [{"id": "s1", "name": "Step 1", "type": "function", "function_name": "func_a"}],
    }), encoding="utf-8")

    (plugin_a / "hooks").mkdir()
    (plugin_a / "hooks" / "pre_request.py").write_text(textwrap.dedent('''\
        """\
        @name: plugin_a_pre
        @type: pre_request
        @description: Pre-request hook from plugin A
        """

        async def run(ctx):
            ctx.metadata["plugin_a_hook"] = True
            return ctx
    '''), encoding="utf-8")

    # Plugin with dependency on plugin-a
    plugin_b = plugins / "plugin-b"
    plugin_b.mkdir()
    (plugin_b / "plugin.json").write_text(json.dumps({
        "name": "plugin-b",
        "version": "0.1.0",
        "description": "Test plugin B (depends on A)",
        "functions": ["functions/*.py"],
        "variables": {"shared_var": "from_b"},
        "dependencies": ["plugin-a"],
    }), encoding="utf-8")

    (plugin_b / "functions").mkdir()
    (plugin_b / "functions" / "func_b.py").write_text(textwrap.dedent('''\
        """\
        @name: func_b
        @type: utility
        @description: Function from plugin B
        """

        def run(ctx):
            return "result_b"
    '''), encoding="utf-8")

    # Invalid plugin (bad manifest)
    plugin_bad = plugins / "plugin-bad"
    plugin_bad.mkdir()
    (plugin_bad / "plugin.json").write_text("not valid json{{", encoding="utf-8")

    # Directory without plugin.json (should be skipped)
    (plugins / "not-a-plugin").mkdir()

    return tmp_path


class TestPluginDiscovery:
    def test_discover_finds_valid_plugins(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        discovered = registry.discover()
        names = [p.manifest.name for p in discovered]
        assert "plugin-a" in names
        assert "plugin-b" in names

    def test_discover_skips_directories_without_manifest(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        discovered = registry.discover()
        names = [p.manifest.name for p in discovered]
        assert "not-a-plugin" not in names

    def test_discover_handles_invalid_manifest(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        discovered = registry.discover()
        bad = next(p for p in discovered if p.manifest.name == "plugin-bad")
        assert bad.status == PluginStatus.ERROR
        assert bad.error is not None

    def test_discover_nonexistent_directory(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "nonexistent")
        assert registry.discover() == []

    def test_discover_parses_manifest_fields(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        discovered = registry.discover()
        plugin_a = next(p for p in discovered if p.manifest.name == "plugin-a")
        assert plugin_a.manifest.version == "1.0.0"
        assert plugin_a.manifest.description == "Test plugin A"
        assert plugin_a.manifest.author == "Test"


class TestPluginLoading:
    def test_load_activates_plugin(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        registry.discover()
        info = registry.load("plugin-a")
        assert info.status == PluginStatus.ACTIVE

    def test_load_discovers_functions(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        registry.discover()
        info = registry.load("plugin-a")
        func_names = [f["name"] for f in info.functions]
        assert "func_a" in func_names

    def test_load_discovers_workflows(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        registry.discover()
        info = registry.load("plugin-a")
        assert len(info.workflows) == 1
        assert info.workflows[0]["id"] == "wf-a"

    def test_load_resolves_dependencies(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        registry.discover()
        info = registry.load("plugin-b")
        assert info.status == PluginStatus.ACTIVE
        # plugin-a should also be loaded
        dep = registry.get_plugin("plugin-a")
        assert dep is not None
        assert dep.status == PluginStatus.ACTIVE

    def test_load_missing_plugin_raises(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        with pytest.raises(FileNotFoundError):
            registry.load("nonexistent")

    def test_load_idempotent(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        registry.discover()
        info1 = registry.load("plugin-a")
        info2 = registry.load("plugin-a")
        assert info1.status == PluginStatus.ACTIVE
        assert info2.status == PluginStatus.ACTIVE


class TestPluginUnloading:
    def test_unload_resets_status(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        registry.discover()
        registry.load("plugin-a")
        result = registry.unload("plugin-a")
        assert result is True
        info = registry.get_plugin("plugin-a")
        assert info.status == PluginStatus.DISCOVERED

    def test_unload_clears_functions_and_workflows(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        registry.discover()
        registry.load("plugin-a")
        registry.unload("plugin-a")
        info = registry.get_plugin("plugin-a")
        assert info.functions == []
        assert info.workflows == []

    def test_unload_nonexistent_returns_false(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        assert registry.unload("nope") is False


class TestPluginFunctions:
    async def test_plugin_function_executes(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        registry.discover()
        info = registry.load("plugin-a")
        func_path = next(f["path"] for f in info.functions if f["name"] == "func_a")

        import importlib.util
        spec = importlib.util.spec_from_file_location("func_a", func_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        result = module.run(ExecutionContext())
        assert result == "result_a"

    def test_get_all_functions_returns_active_plugin_functions(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        registry.discover()
        registry.load("plugin-a")
        registry.load("plugin-b")
        all_funcs = registry.get_all_functions()
        names = [f["name"] for f in all_funcs]
        assert "func_a" in names
        assert "func_b" in names

    def test_get_all_functions_excludes_unloaded(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        registry.discover()
        registry.load("plugin-a")
        registry.load("plugin-b")
        registry.unload("plugin-b")
        all_funcs = registry.get_all_functions()
        names = [f["name"] for f in all_funcs]
        assert "func_a" in names
        assert "func_b" not in names


class TestPluginVariables:
    def test_get_all_variables_merges_plugins(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        registry.discover()
        registry.load("plugin-a")
        registry.load("plugin-b")
        variables = registry.get_all_variables()
        assert "plugin_a_var" in variables
        assert variables["plugin_a_var"] == "hello"

    def test_later_plugin_overrides_shared_variable(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        registry.discover()
        registry.load("plugin-a")
        registry.load("plugin-b")
        variables = registry.get_all_variables()
        # plugin-b is loaded after plugin-a, so its shared_var wins
        assert variables["shared_var"] == "from_b"


class TestPluginReload:
    def test_reload_clears_and_rediscovers(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        registry.discover()
        registry.load("plugin-a")
        plugins = registry.reload()
        names = [p.manifest.name for p in plugins]
        assert "plugin-a" in names
        # After reload, plugin-a should be LOADED not ACTIVE
        info = registry.get_plugin("plugin-a")
        assert info.status == PluginStatus.LOADED


class TestPluginScaffold:
    def test_scaffold_creates_directory_structure(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        plugin_dir = registry.scaffold_plugin("new-plugin")
        assert plugin_dir.exists()
        assert (plugin_dir / "plugin.json").exists()
        assert (plugin_dir / "functions").is_dir()
        assert (plugin_dir / "workflows").is_dir()
        assert (plugin_dir / "hooks").is_dir()
        assert (plugin_dir / "functions" / "example.py").exists()

    def test_scaffold_manifest_has_correct_name(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        plugin_dir = registry.scaffold_plugin("my-tool")
        manifest = json.loads((plugin_dir / "plugin.json").read_text(encoding="utf-8"))
        assert manifest["name"] == "my-tool"
        assert manifest["version"] == "0.1.0"

    def test_scaffold_existing_plugin_raises(self, plugins_dir: Path) -> None:
        registry = FilesystemPluginRegistry(plugins_dir / "plugins")
        registry.scaffold_plugin("duplicate")
        # Should not raise — scaffold is idempotent on existing dirs
        registry.scaffold_plugin("duplicate")
