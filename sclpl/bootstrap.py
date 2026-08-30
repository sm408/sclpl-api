"""Loading what a run can reach: built-in functions, then plugins.

One explicit call rather than import side effects scattered around the package. The
order matters and is worth stating: built-ins register first, so a plugin that shadows
one is doing it deliberately and can be reported as such.

Idempotent, because the CLI, the tests, and an embedded caller all want to be able to
say "make sure everything is loaded" without coordinating.
"""

from __future__ import annotations

_LOADED = False


def load(*, plugins: bool = True) -> None:
    """Register the built-in functions, and discover plugins."""
    global _LOADED
    if _LOADED:
        return
    _LOADED = True

    # Registers every operator family. Importing is the registration.
    import sclpl.expr  # noqa: F401
    import sclpl.functions  # noqa: F401

    # Registers the Parquet reader with `values/ref.py`, so a spilled table can come
    # back without `values/` ever importing `tables/`.
    import sclpl.tables  # noqa: F401

    if plugins:
        _load_plugins()


def _load_plugins() -> None:
    """Plugin discovery, once M8 has provided it.

    Guarded rather than assumed so the engine is usable without the plugin layer --
    which is also what proves the built-ins do not secretly depend on it.
    """
    try:
        from sclpl.ext.plugins import discover  # type: ignore[import-not-found]
    except ImportError:
        return
    discover()


def reset() -> None:
    """Forget that loading happened. For tests that need a clean registry."""
    global _LOADED
    _LOADED = False
