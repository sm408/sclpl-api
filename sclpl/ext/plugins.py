"""Finding plugins, checking they fit, and letting them register.

Three places are searched, in this order (SPEC section 11):

1. `importlib.metadata.entry_points(group="sclpl.plugins")` -- anything `pip install`ed
2. `./plugins/` -- the one you are writing, in the project you are writing it for
3. `~/.sclpl/plugins/` -- the ones you keep

The order matters only for shadowing, and shadowing is reported rather than silent: two
plugins claiming one name is a thing to know about, not a coin toss.

**There is no sandbox.** A plugin is trusted code -- it is a Python package the user
chose to install, and anything that could sandbox it could be bypassed by it. What there
*is* is a declaration: a plugin says which capabilities it needs, `sclpl plugin list`
shows them, and `--deny-capability network` refuses to load anything that asked for one
you did not want. That is an honest guarantee about *loading*, which is a different and
smaller claim than a guarantee about *running*, and it is the one that can actually be
kept.

**The ABI is a single integer.** `api = "sclpl/1"`. A plugin built against an API that no
longer exists fails at load with the versions named, rather than at the first call with
an `AttributeError` from inside somebody else's package.
"""

from __future__ import annotations

import sys
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sclpl.errors import ValidationError, did_you_mean

#: What this build of `sclpl` implements. A plugin declaring a different major number is
#: refused; there is no compatibility shim, because a shim that half-works is worse than
#: a message saying which version to install.
API_VERSION = 1
API_STRING = f"sclpl/{API_VERSION}"

#: Everything a plugin may declare. Unknown capabilities are refused rather than
#: ignored: a typo in a manifest should not silently widen or narrow what is granted.
CAPABILITIES = frozenset(
    {
        "network",
        "fs:read",
        "fs:write",
        "secrets:read",
        "subprocess",
    }
)

MANIFEST = "plugin.toml"

#: Where local plugins live, in search order after entry points.
LOCAL_DIRS = ("plugins", "~/.sclpl/plugins")


@dataclass(slots=True)
class Contribution:
    """One thing a plugin adds: a connector, a paginator, an auth provider."""

    kind: str
    name: str
    lane: str | None = None
    summary: str = ""


@dataclass(slots=True)
class Plugin:
    """A discovered plugin, whether or not it loaded."""

    name: str
    version: str = "0"
    api: str = API_STRING
    capabilities: frozenset[str] = frozenset()
    source: str = "entry-point"
    path: Path | None = None
    module: str = ""
    description: str = ""
    contributes: list[Contribution] = field(default_factory=list)
    #: Set when the plugin was found but not loaded, and why.
    refused: str = ""
    loaded: bool = False

    @property
    def api_major(self) -> int:
        _, _, number = self.api.partition("/")
        try:
            return int(number.split(".")[0])
        except ValueError:
            return -1

    def describe(self) -> str:
        caps = ", ".join(sorted(self.capabilities)) or "none"
        return f"{self.name} {self.version} [{self.source}] capabilities: {caps}"


@dataclass(slots=True)
class Registry:
    """Everything found, in the order it was found."""

    plugins: dict[str, Plugin] = field(default_factory=dict)
    #: Names claimed twice, and by whom. Reported, never silently resolved.
    shadowed: list[tuple[str, str, str]] = field(default_factory=list)

    def add(self, plugin: Plugin) -> None:
        existing = self.plugins.get(plugin.name)
        if existing is not None:
            self.shadowed.append((plugin.name, existing.source, plugin.source))
            return
        self.plugins[plugin.name] = plugin

    def loaded(self) -> list[Plugin]:
        return [plugin for plugin in self.plugins.values() if plugin.loaded]

    def refused(self) -> list[Plugin]:
        return [plugin for plugin in self.plugins.values() if plugin.refused]

    def get(self, name: str) -> Plugin:
        found = self.plugins.get(name)
        if found is None:
            remedies = []
            suggestion = did_you_mean(name, list(self.plugins))
            if suggestion:
                remedies.append(suggestion)
            remedies.append("run 'sclpl plugin list' to see what is installed")
            raise ValidationError(f"no plugin named {name!r}", remedies=remedies)
        return found


REGISTRY = Registry()

#: What this process refuses, from `--deny-capability`. Held here rather than passed
#: around because discovery happens more than once -- at startup, and again whenever
#: `plugin list` wants a fresh view -- and a denial that applied only to the first would
#: be a denial that `plugin list` could not see.
DENIED: set[str] = set()


def discover(
    *,
    denied: Iterable[str] | None = None,
    include_bundled: bool = True,
    extra_dirs: Iterable[Path] = (),
    activate: bool = True,
) -> Registry:
    """Find plugin metadata, activating compatible plugins only when requested.

    Never raises for a bad plugin. One plugin with a malformed manifest should not stop
    a run that does not use it -- it is recorded as refused, listed by `plugin list`, and
    the run continues. Failing the whole engine because something optional is broken is
    the wrong trade.
    """
    if denied is not None:
        DENIED.update(denied)
    denied_set = frozenset(DENIED)
    REGISTRY.plugins.clear()
    REGISTRY.shadowed.clear()

    if include_bundled:
        for found in _bundled():
            REGISTRY.add(found)
    for found in _entry_points():
        REGISTRY.add(found)
    for directory in [*_local_dirs(), *extra_dirs]:
        for found in _from_directory(directory):
            REGISTRY.add(found)

    if activate:
        for plugin in REGISTRY.plugins.values():
            _load(plugin, denied_set)
    return REGISTRY


def _load(plugin: Plugin, denied: frozenset[str]) -> None:
    """Check it fits, then import it. Anything wrong is recorded, not raised."""
    if plugin.refused:
        # Already refused while its manifest was read. Continuing would overwrite the
        # actual problem -- unreadable TOML -- with a symptom of it, such as "names no
        # module", and send the reader to the wrong line.
        return
    if plugin.api_major != API_VERSION:
        plugin.refused = (
            f"built for {plugin.api} but this is {API_STRING}; "
            "install a matching version of the plugin"
        )
        return

    unknown = plugin.capabilities - CAPABILITIES
    if unknown:
        plugin.refused = (
            f"declares unknown capabilit{'y' if len(unknown) == 1 else 'ies'} "
            f"{', '.join(sorted(unknown))}; known: {', '.join(sorted(CAPABILITIES))}"
        )
        return

    refused = plugin.capabilities & denied
    if refused:
        plugin.refused = f"needs {', '.join(sorted(refused))}, which this run denied"
        return

    if not plugin.module:
        plugin.refused = "the manifest names no module to import"
        return

    try:
        module = _import(plugin)
    except Exception as error:  # noqa: BLE001 - one broken plugin is not a broken engine
        plugin.refused = f"failed to import: {type(error).__name__}: {error}"
        return

    register = getattr(module, "register", None)
    if callable(register):
        try:
            register()
        except Exception as error:  # noqa: BLE001
            plugin.refused = f"register() raised {type(error).__name__}: {error}"
            return

    plugin.loaded = True


def _import(plugin: Plugin) -> Any:
    """Import a plugin's module, adding its directory to the path if it needs one."""
    import importlib

    if plugin.path is not None:
        root = str(plugin.path.parent)
        if root not in sys.path:
            sys.path.insert(0, root)
    return importlib.import_module(plugin.module)


# -- the three sources -------------------------------------------------------------


def _bundled() -> list[Plugin]:
    """The plugins that ship with `sclpl`.

    They go through exactly the same discovery, manifest, and capability path as any
    other. That is the point of shipping them: if a bundled plugin needs something the
    public API does not offer, the API is wrong, and we find out before anyone else does.
    """
    root = Path(__file__).resolve().parent.parent / "plugins_bundled"
    if not root.is_dir():
        return []
    return [
        plugin
        for directory in sorted(root.iterdir())
        if directory.is_dir() and (plugin := _read_manifest(directory, "bundled")) is not None
    ]


def _entry_points() -> list[Plugin]:
    from importlib.metadata import entry_points

    found: list[Plugin] = []
    try:
        points = entry_points(group="sclpl.plugins")
    except TypeError:  # pragma: no cover - very old importlib.metadata
        return found

    for point in points:
        plugin = Plugin(name=point.name, module=point.value, source="entry-point")
        # Inspection must never import plugin code. Activation happens only after the
        # caller applies policy and explicitly chooses it.
        try:
            if point.dist is None:
                found.append(plugin)
                continue
            manifest = point.dist.locate_file(f"{point.name}/{MANIFEST}")
        except Exception:  # noqa: BLE001 - loading to find the manifest must not throw
            found.append(plugin)
            continue
        described = _read_manifest(Path(manifest.parent), "entry-point")
        if described is not None:
            described.module = point.value
            described.name = described.name or point.name
            found.append(described)
        else:
            found.append(plugin)
    return found


def _local_dirs() -> list[Path]:
    return [Path(entry).expanduser() for entry in LOCAL_DIRS]


def _from_directory(root: Path) -> list[Plugin]:
    if not root.is_dir():
        return []
    source = "local" if root.name == "plugins" else "user"
    return [
        plugin
        for directory in sorted(root.iterdir())
        if directory.is_dir() and (plugin := _read_manifest(directory, source)) is not None
    ]


def _read_manifest(directory: Path, source: str) -> Plugin | None:
    """Parse `plugin.toml`, or None if there is not one.

    A malformed manifest produces a *refused* plugin rather than nothing, so `plugin
    list` can say what is wrong with it. Silently skipping it would leave someone
    wondering why their plugin does not appear.
    """
    manifest = directory / MANIFEST
    if not manifest.is_file():
        return None

    try:
        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError) as error:
        return Plugin(
            name=directory.name,
            source=source,
            path=directory,
            refused=f"{MANIFEST} is not readable: {error}",
        )

    block = data.get("plugin", {})
    if not isinstance(block, dict):
        return Plugin(
            name=directory.name,
            source=source,
            path=directory,
            refused=f"{MANIFEST} has no [plugin] table",
        )

    plugin = Plugin(
        name=str(block.get("name") or directory.name),
        version=str(block.get("version", "0")),
        api=str(block.get("api", API_STRING)),
        capabilities=frozenset(str(item) for item in block.get("capabilities", [])),
        source=source,
        path=directory,
        module=str(block.get("module") or directory.name),
        description=str(block.get("description", "")),
    )

    for kind in ("connector", "function", "verb", "auth", "paginator", "backend"):
        for entry in data.get(kind, []):
            if isinstance(entry, dict):
                plugin.contributes.append(
                    Contribution(
                        kind=kind,
                        name=str(entry.get("name", "")),
                        lane=entry.get("lane"),
                        summary=str(entry.get("summary", "")),
                    )
                )
    return plugin


def parse_capabilities(values: Iterable[str]) -> frozenset[str]:
    """Validate `--deny-capability` values, so a typo is not a silent no-op."""
    wanted = frozenset(values)
    unknown = wanted - CAPABILITIES
    if unknown:
        remedies = []
        suggestion = did_you_mean(sorted(unknown)[0], sorted(CAPABILITIES))
        if suggestion:
            remedies.append(suggestion)
        remedies.append(f"known capabilities: {', '.join(sorted(CAPABILITIES))}")
        raise ValidationError(
            f"unknown capabilit{'y' if len(unknown) == 1 else 'ies'}: {', '.join(sorted(unknown))}",
            remedies=remedies,
        )
    return wanted
