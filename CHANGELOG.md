# Changelog

This project follows a small, human-readable changelog. The supported public
release lineage begins at `v1.0.0`.

## Unreleased

## 1.0.1

- Built on the retained `v1.0.0` TUI-only release lineage; this is the first
  current CLI/runtime/editor-support release in that line.

- Added source metadata and passive registry introspection used by the separately released
  SCLPLL language server and VS Code extension in `sm408/sclpll-extras`.
- Added safe plugin-manifest callable signature and parameter metadata for editor help.
- Clarified that editor tooling, plugins, and the public function catalogue are distributed
  through `sclpll-extras`; built-in functions remain included in the core runtime.

- Added: registered, SHA-256-pinned ordinary Python scripts can run with `sclpl python NAME [ARGS...]`, or
  participate in a workflow through the built-in `python` function. Workflow values cross the
  script boundary as JSON on stdin/stdout; scripts run in the active SCLPL Python environment.
- Fixed: raised the `pyarrow` dependency floor to `>=22,<26` so installation succeeds
  on Python 3.14, where no wheel exists below `pyarrow` 22.
- Fixed: a failed `assert` step's remedy claimed `-vv` would show the values it was
  checking; it now actually does, as a bounded, redaction-aware debug log line.
- Fixed: `mypy` failed on Linux (as CI runs it) over the Windows-only `msvcrt` import
  in `state/locking.py`, an `importlib.metadata` typing change in `ext/plugins.py`,
  and missing annotations in `test_test_manifests.py` -- all pre-existing, surfaced
  once the also-pre-existing `ruff format` drift ahead of them was fixed.
- Fixed: declaring a `policy.output_roots` entry that is a symlink to a location
  outside the project (the ordinary shape of a mounted Docker/Kubernetes volume)
  failed to parse at all, refusing every workflow run in that project outright.
  `check_output`'s resolved-path comparison against the declared roots already
  enforced the real security boundary; the root's own location no longer has to
  stay inside the project tree to be declared, and a write reached through that
  declared symlink is correctly allowed rather than denied.
- Fixed: two runs recorded in the same second (`started_at` has one-second
  resolution) could come back from `runs`/history queries in either order,
  since nothing broke the tie -- `history recent`, `find`, `search`,
  `producers_of`, and `prune` now all break a timestamp tie by insertion order,
  so "most recent" is deterministic instead of whatever a tied `ORDER BY`
  scan happened to return.
- Added: a `sleep(ms)` built-in function that pauses a step for the given number of
  milliseconds, then returns it. Runs on the event-loop lane, so it costs nothing but
  the calling step's own progress -- every other step keeps running while it waits.
- Continued documentation and repository maintenance.

## 1.0.0 — TUI-only release

- Retained as the foundation of the current public release lineage.
