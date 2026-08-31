---
tags:
  - milestone
---

# M0 Deletion

Commit `5a19bcc`. **250 files, 59,093 lines removed.**

## What went

The Textual TUI, the FastAPI backend, the Vue SPA — and `app/`, the package they were
entangled with.

The whole of `app/` went, not just `app/ui/` and `app/web/`. It was not separable:
`services/` imported `app.web.errors`; the SCLPLL v1 compiler imported `app.ui.app`.
SPEC §4's "repository layout after M0" contains no `app/`, so the deletion is what the
spec already called for.

## What was kept

- Baseline commit `1b1abe0` is the full archive and must not be deleted
- `docs/attic/carried/` holds the two named carry-overs: `sclpll_v1_compiler.py` (for
  M4's SCLPLL work) and `storage/` (for M9's `state/db.py`)
- v1 docs, examples, workflows, functions, and plugins live under `docs/attic/`

## What was written

~1,000 lines across `sclpl/cli/` and `sclpl/render/`, plus 77 tests. The five CI gates
were stood up in the same commit, on 3.11 and 3.13.

## Why deleted rather than deprecated

[[Locked Decisions#6 TUI, FastAPI, and SPA are deleted, not deprecated]]. Deprecation
means keeping them working. Three surfaces over one engine is three places for every
behaviour to drift, and the engine underneath was being replaced anyway.

## The bar it set

> **Nothing is stubbed.** If `--help` lists a command, that command works.

M0 ended with `run`, `validate`, `explain`, `fmt`, and `convert` **not registered at
all** rather than registered and failing. The bare launcher printed help and exited 2 —
the documented non-TTY behaviour — because the menu belonged to M4 alongside the
catalogue it lists.
