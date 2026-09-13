# Changelog

This project follows a small, human-readable changelog. The supported public
release lineage begins at `v1.0.0`.

## Unreleased

## 1.0.2

- Added: `sclpl package build|validate|install|list|show|verify|remove|update|
  pull|release-index` -- a content-addressed, deterministic package format
  (fixed timestamps, sorted entries, a manifest of per-file and aggregate
  SHA-256 digests) for bundling a project's workflows, tests, fixtures,
  schemas, docs, and plugins into one archive, installing it elsewhere, and
  verifying it later.
- Added: `sclpl import --from curl|openapi|postman` renders a saved curl
  command, one operation from a local OpenAPI 3.x document, or one request
  from a local Postman v2.1 collection into a workflow. Extracted
  credentials become named `[auth.*]` references, never literal values in
  the generated workflow.
- Added: `[notifications.<name>]` -- opt-in webhook, Slack webhook, or SMTP
  notifications on `run_started`, `run_finished`, or `step_failed`, with
  bounded retries and a delivery receipt logged after every run
  (`info`/`warning`) that never changes the run's own exit code.
- Added: `sclpl test list|validate|run` (project `*.test.toml` manifests,
  executed offline against a fixture) gained `--junit`/`--json`/`--html`
  report output, and `sclpl project ci-template` writes a ready-to-use,
  offline GitHub Actions workflow for a generated project.
- Added: five complete, runnable business-acceptance examples under
  `examples/journeys/`, each with a recorded offline fixture, a required
  failure case, and automated test coverage -- API-to-CSV reporting, API
  reconciliation, API quality monitoring, lightweight ingestion under
  validated publish, and package/install/replay integration regression
  testing.
- Fixed: `examples/13-python-script.py`'s pinned SHA-256 broke on every
  Windows checkout, because git's default `core.autocrlf` silently rewrote
  its LF line endings to CRLF before the digest was ever checked. Added a
  root `.gitattributes` (`*.py text eol=lf`) instead of touching the hash.
- Fixed: `@var name = "{{secret('x')}}"` never actually resolves --
  `{{...}}` expands once, so a `@var` holding template syntax is substituted
  back out as literal text rather than re-evaluated. `examples/11-cache-
  retry-and-secret.sclpll` used exactly this pattern and had never been run
  against a live or replayed server; fixed by calling `secret()` at the
  point of use instead.
- Changed: CI now runs the full suite on Linux, Windows, and macOS (was
  Linux-only), plus a bare-install job with no optional extra at all, and
  gates on the generated reference documentation staying current.
- Added: `scripts/benchmark.py`, a runnable (not CI-gating) harness for the
  performance budgets proposed alongside the packaging/import/notification
  work -- synthetic workflow throughput, paginated-fetch throughput,
  streaming peak memory, retained run-history query latency, and replay
  dispatch cost.
- Known limitation: on Windows, `CTRL_BREAK_EVENT` -- the only console
  control event that can reach a process outside the sender's own console
  group -- maps to `SIGBREAK`, which Python does not auto-raise as
  `KeyboardInterrupt`. A supervisor using it for a graceful shutdown
  currently gets a hard, unrecorded process kill rather than sclpl's normal
  interrupted-with-cleanup exit path. A local Ctrl-C is unaffected.

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
