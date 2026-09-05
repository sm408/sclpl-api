"""Loading what a run can reach: built-in functions, then plugins.

One explicit call rather than import side effects scattered around the package. The
order matters and is worth stating: built-ins register first, so a plugin that shadows
one is doing it deliberately and can be reported as such.

Idempotent, because the CLI, the tests, and an embedded caller all want to be able to
say "make sure everything is loaded" without coordinating.
"""

from __future__ import annotations

from collections.abc import Iterable

_BUILTINS_LOADED = False
_PLUGINS_LOADED = False


def load(*, plugins: bool = True, denied: Iterable[str] = ()) -> None:
    """Register the built-in functions, and discover plugins.

    ``denied`` names capabilities a plugin may not have. It has to be known *here*,
    before anything is imported: importing a plugin runs its module, and a capability
    refused after that has already been exercised. That is why `--deny-capability` is
    read from the command line before this is called rather than through the option
    parser -- the denial has to precede the import, and the parser runs after it.
    """
    global _BUILTINS_LOADED
    if not _BUILTINS_LOADED:
        _BUILTINS_LOADED = True

        # Registers every operator family. Importing is the registration.
        import sclpl.expr  # noqa: F401
        import sclpl.functions  # noqa: F401

        # Registers the Parquet reader with `values/ref.py`, so a spilled table can
        # come back without `values/` ever importing `tables/`.
        import sclpl.tables  # noqa: F401

    if plugins:
        activate_plugins(denied=denied)


def activate_plugins(*, denied: Iterable[str] = ()) -> None:
    """Activate plugins after the caller has resolved and enforced policy."""
    global _PLUGINS_LOADED
    load(plugins=False)
    if _PLUGINS_LOADED:
        return
    _PLUGINS_LOADED = True
    _load_plugins(denied)


def _load_plugins(denied: Iterable[str] = ()) -> None:
    """Plugin discovery, once M8 has provided it.

    Guarded rather than assumed so the engine is usable without the plugin layer --
    which is also what proves the built-ins do not secretly depend on it.
    """
    try:
        from sclpl.ext.plugins import discover
    except ImportError:
        return
    discover(denied=denied)


def reset() -> None:
    """Forget that loading happened. For tests that need a clean registry."""
    global _BUILTINS_LOADED, _PLUGINS_LOADED
    _BUILTINS_LOADED = False
    _PLUGINS_LOADED = False
