# Changelog

This project follows a small, human-readable changelog. Releases will use semantic versioning
once the public package API is declared stable.

## Unreleased

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

## 0.9.1

- Added provider-neutral remote workflow and port resource support.
- Added controlled local staging and revision-aware provider publication.
- Added the optional Azure Blob resource plugin (`azblob://`).

## 0.1.0

- CLI workflow runner for HTTP APIs with JSON and SCLPLL workflow surfaces.
- Typed values, dependency-driven scheduling, retries, pagination, control flow, and caching.
- Table transforms and exports for CSV, JSON, NDJSON, Parquet, Excel, and SQLite.
- Python function extensions and capability-declared plugins.
- Local run history, secret storage, redaction, generated references, and CI quality gates.
