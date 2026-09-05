# ADR 0003 — Establish project-format ownership for the unified upgrade

- **Date:** 2026-09-05
- **Status:** accepted
- **Supersedes in part:** [ADR 0002](0002-budget-the-sclpll-surface-separately.md)

## Decision

The unified 2.1 upgrade owns all new persistent data formats explicitly. `sclpl.toml`
uses `project.schema = 1`; a reader refuses an unknown schema rather than guessing.
Future fixture, lock, artifact, package, checkpoint, and history formats must each carry
their own integer schema version and must reject a newer version before use. A format
upgrade requires a migration/rollback note and a compatibility test.

Project configuration is budgeted as `sclpl/project/` with 1,200 counted code lines.
The CLI budget rises from 1,400 to 1,800: its measured 69-line headroom cannot contain
the new command wiring. The total budget becomes 18,400 lines: 16,000 from ADR 0002,
1,200 for the new package, and 1,200 for the project command surface. `check_budget.py`
now fails if any top-level Python package has no budget, preventing new code from
escaping the gate.

`check_layering.py` now reports arbitrary directed cycles, not only reciprocal pairs.
Root-entrypoint edges remain excluded as documented; all other directed cycles fail CI.

## Consequences

`sclpl init`, project discovery, environment selection, and configuration precedence
share one strict loader. A project-relative path resolves from the manifest root and
cannot escape it. Secrets are references outside the manifest and are never emitted by
`project check --json`.

The format/version rule applies to every later batch. It does not make a project manifest
or a package version interchangeable with the SCLPLL language version or plugin ABI.
