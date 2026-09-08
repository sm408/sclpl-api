# Changelog

This project follows a small, human-readable changelog. Releases will use semantic versioning
once the public package API is declared stable.

## Unreleased

- Fixed: raised the `pyarrow` dependency floor to `>=22,<26` so installation succeeds
  on Python 3.14, where no wheel exists below `pyarrow` 22.
- Continued documentation and repository maintenance.

## 0.1.0

- CLI workflow runner for HTTP APIs with JSON and SCLPLL workflow surfaces.
- Typed values, dependency-driven scheduling, retries, pagination, control flow, and caching.
- Table transforms and exports for CSV, JSON, NDJSON, Parquet, Excel, and SQLite.
- Python function extensions and capability-declared plugins.
- Local run history, secret storage, redaction, generated references, and CI quality gates.

