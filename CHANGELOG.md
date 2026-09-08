# Changelog

This project follows a small, human-readable changelog. Releases will use semantic versioning
once the public package API is declared stable.

## Unreleased

- Fixed: raised the `pyarrow` dependency floor to `>=22,<26` so installation succeeds
  on Python 3.14, where no wheel exists below `pyarrow` 22.
- Fixed: a project/output lock file (`.sclpl-lock`) no longer stays behind forever
  next to real output files after a run releases it.
- Fixed: a failed `assert` step's remedy claimed `-vv` would show the values it was
  checking; it now actually does, as a bounded, redaction-aware debug log line.
- Fixed: `mypy` failed on Linux (as CI runs it) over the Windows-only `msvcrt` import
  in `state/locking.py`, an `importlib.metadata` typing change in `ext/plugins.py`,
  and missing annotations in `test_test_manifests.py` -- all pre-existing, surfaced
  once the also-pre-existing `ruff format` drift ahead of them was fixed.
- Continued documentation and repository maintenance.

## 0.1.0

- CLI workflow runner for HTTP APIs with JSON and SCLPLL workflow surfaces.
- Typed values, dependency-driven scheduling, retries, pagination, control flow, and caching.
- Table transforms and exports for CSV, JSON, NDJSON, Parquet, Excel, and SQLite.
- Python function extensions and capability-declared plugins.
- Local run history, secret storage, redaction, generated references, and CI quality gates.

