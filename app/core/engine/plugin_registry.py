from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.contracts.plugin_registry import PluginRegistry
from app.core.engine.function_runner import FilesystemFunctionRunner
from app.core.models.context import ExecutionContext
from app.core.models.plugin import PluginInfo, PluginManifest, PluginStatus

logger = logging.getLogger(__name__)


class FilesystemPluginRegistry(PluginRegistry):
    def __init__(self, base_dir: str | Path = "plugins") -> None:
        self._base = Path(base_dir)
        self._plugins: dict[str, PluginInfo] = {}

    def discover(self) -> list[PluginInfo]:
        if not self._base.exists():
            return []

        discovered: list[PluginInfo] = []
        for plugin_dir in self._base.iterdir():
            if not plugin_dir.is_dir():
                continue
            manifest_path = plugin_dir / "plugin.json"
            if not manifest_path.exists():
                continue

            try:
                info = self._load_manifest(plugin_dir)
                self._plugins[info.manifest.name] = info
                discovered.append(info)
            except Exception as exc:
                logger.warning("Failed to discover plugin in %s: %s", plugin_dir, exc)
                info = PluginInfo(
                    manifest=PluginManifest(name=plugin_dir.name, version="0.0.0", path=str(plugin_dir)),
                    status=PluginStatus.ERROR,
                    error=str(exc),
                )
                self._plugins[plugin_dir.name] = info
                discovered.append(info)

        return discovered

    def load(self, name: str) -> PluginInfo:
        if name in self._plugins and self._plugins[name].status == PluginStatus.ACTIVE:
            return self._plugins[name]

        plugin_dir = self._base / name
        if not plugin_dir.exists():
            raise FileNotFoundError(f"Plugin directory not found: {plugin_dir}")

        info = self._load_manifest(plugin_dir)
        self._validate_dependencies(info)
        self._load_functions(info)
        self._load_workflows(info)

        info.status = PluginStatus.ACTIVE
        self._plugins[name] = info
        return info

    def unload(self, name: str) -> bool:
        if name not in self._plugins:
            return False
        info = self._plugins[name]
        info.status = PluginStatus.DISCOVERED
        info.functions = []
        info.workflows = []
        return True

    def list_plugins(self) -> list[PluginInfo]:
        if not self._plugins:
            self.discover()
        return list(self._plugins.values())

    def get_plugin(self, name: str) -> PluginInfo | None:
        if not self._plugins:
            self.discover()
        return self._plugins.get(name)

    def get_all_functions(self) -> list[dict[str, str]]:
        functions: list[dict[str, str]] = []
        for info in self._plugins.values():
            if info.status == PluginStatus.ACTIVE:
                functions.extend(info.functions)
        return functions

    def get_all_variables(self) -> dict[str, str]:
        variables: dict[str, str] = {}
        for info in self._plugins.values():
            if info.status == PluginStatus.ACTIVE:
                variables.update(info.manifest.variables)
        return variables

    def get_hook_runner(self, hook_type: str, base_dir: str | Path | None = None):
        runner = FilesystemFunctionRunner(base_dir or self._base)
        hook_funcs: list[dict[str, str]] = []

        for info in self._plugins.values():
            if info.status != PluginStatus.ACTIVE:
                continue
            hook_path = info.manifest.hooks.get(hook_type)
            if not hook_path:
                continue

            full_path = Path(info.manifest.path) / hook_path
            if full_path.exists():
                try:
                    import importlib.util
                    import time

                    spec = importlib.util.spec_from_file_location(f"plugin_hook_{info.manifest.name}_{hook_type}", full_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    if hasattr(module, "run"):
                        hook_funcs.append({
                            "name": f"plugin_{info.manifest.name}_{hook_type}",
                            "path": str(full_path),
                            "module": module,
                        })
                except Exception as exc:
                    logger.warning("Failed to load hook %s from plugin %s: %s", hook_type, info.manifest.name, exc)

        return hook_funcs

    def reload(self) -> list[PluginInfo]:
        self._plugins.clear()
        return self.discover()

    def scaffold_plugin(self, name: str) -> Path:
        plugin_dir = self._base / name
        plugin_dir.mkdir(parents=True, exist_ok=True)

        (plugin_dir / "functions").mkdir(exist_ok=True)
        (plugin_dir / "workflows").mkdir(exist_ok=True)
        (plugin_dir / "hooks").mkdir(exist_ok=True)

        manifest = {
            "name": name,
            "version": "0.1.0",
            "description": f"{name} plugin",
            "author": "",
            "functions": ["functions/*.py"],
            "workflows": ["workflows/*.sclpll"],
            "hooks": {},
            "variables": {},
            "dependencies": [],
        }
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        (plugin_dir / "functions" / "example.py").write_text(
            '"""\n'
            '@name: example\n'
            '@type: utility\n'
            '@description: Example plugin function\n'
            '"""\n'
            '\n'
            'def run(ctx):\n'
            '    return {"status": "ok", "plugin": "' + name + '"}\n',
            encoding="utf-8",
        )

        (plugin_dir / "README.md").write_text(
            f"# {name}\n\nPlugin created by SCLPLAPI scaffold.\n",
            encoding="utf-8",
        )

        return plugin_dir

    def _load_manifest(self, plugin_dir: Path) -> PluginInfo:
        manifest_path = plugin_dir / "plugin.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))

        manifest = PluginManifest(
            name=data.get("name", plugin_dir.name),
            version=data.get("version", "0.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            functions=data.get("functions", []),
            workflows=data.get("workflows", []),
            hooks=data.get("hooks", {}),
            variables=data.get("variables", {}),
            dependencies=data.get("dependencies", []),
            path=str(plugin_dir),
        )

        return PluginInfo(
            manifest=manifest,
            status=PluginStatus.LOADED,
        )

    def _load_functions(self, info: PluginInfo) -> None:
        plugin_path = Path(info.manifest.path)
        runner = FilesystemFunctionRunner(plugin_path)

        for pattern in info.manifest.functions:
            for py_file in plugin_path.glob(pattern):
                if py_file.name.startswith("_"):
                    continue
                meta = runner._parse_metadata(py_file)
                if meta:
                    meta["plugin"] = info.manifest.name
                    info.functions.append(meta)

    def _load_workflows(self, info: PluginInfo) -> None:
        plugin_path = Path(info.manifest.path)

        for pattern in info.manifest.workflows:
            for wf_file in plugin_path.glob(pattern):
                try:
                    import json as _json
                    data = _json.loads(wf_file.read_text(encoding="utf-8"))
                    data["_plugin"] = info.manifest.name
                    data["_path"] = str(wf_file)
                    info.workflows.append(data)
                except Exception as exc:
                    logger.warning("Failed to load workflow %s: %s", wf_file, exc)

    def _validate_dependencies(self, info: PluginInfo) -> None:
        for dep in info.manifest.dependencies:
            dep_dir = self._base / dep
            if not dep_dir.exists():
                raise FileNotFoundError(f"Plugin dependency '{dep}' not found")

            dep_info = self._plugins.get(dep)
            if dep_info is None or dep_info.status != PluginStatus.ACTIVE:
                dep_info = self.load(dep)
                if dep_info.status != PluginStatus.ACTIVE:
                    raise RuntimeError(f"Plugin dependency '{dep}' failed to load")
