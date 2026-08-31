---
tags:
  - start
---

# Why a Rewrite

`sclpl` replaces an earlier engine plus a Textual TUI and a Vue/FastAPI studio. The
predecessor is preserved whole at commit `1b1abe0`; [[M0 Deletion]] removed 250 files
and 59,093 lines from the working tree.

The case for rewriting rather than porting is four defects, each of which independently
blocked a feature the tool needed. All four were verified present at the baseline
commit before any code was written.

| # | Defect | Where it lived | What it blocked |
|---|---|---|---|
| 1 | Every value was stringified between steps | `app/core/models/context.py:24` | Comparisons, arithmetic, sorting, dataframes |
| 2 | The scheduler ran in barrier waves | `app/core/engine/parallel_workflow.py:60` | "Start the moment dependencies are ready" |
| 3 | A new `AsyncClient` per request | `app/services/request_executor.py:33` | Throughput |
| 4 | Secrets silently fell back to base64 | `app/core/secrets.py:38` | Credential safety |

Each defect has a corresponding invariant that exists to keep it dead:

- Defect 1 → [[Invariants#2 Values keep their Python type]] → [[Typed Values]]
- Defect 2 → [[The Scheduler]]
- Defect 3 → [[Transport]]
- Defect 4 → [[Secrets]] #todo *(M9)*

## Why the UI went too

The TUI and the SPA were not separable from the engine. `services/` imported
`app.web.errors`; the SCLPLL compiler imported `app.ui.app`. Deleting the UI meant
deleting `app/`, which is what [[M0 Deletion]] did — and what the SPEC's target tree
already described.

The deeper reason is in [[Locked Decisions#6 TUI, FastAPI, and SPA are deleted, not deprecated]]:
three surfaces over one engine is three places for every behaviour to drift.
