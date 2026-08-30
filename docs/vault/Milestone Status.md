# Milestone Status

Ten milestones, M0 through M9. Each one **registers its surface when it implements it** —
if `--help` lists a command, that command works.

| | Milestone | State | Commit |
|---|---|---|---|
| M0 | [[M0 Deletion]] — delete the UI, stand up the skeleton | ✅ | `5a19bcc` |
| M1 | Typed values and the expression engine | ✅ | `f6c18da` |
| M2 | Continuous scheduling and pooled transport | ✅ | `87a0a5a` |
| M3 | The live region | ✅ | `41d7745` |
| M4 | IR, both surfaces, catalogue, modes, ports, launcher | ✅ | `773e747` |
| M5 | [[M5 Functions and Tables]] | ✅ | `86b9efa` |
| M6 | [[M6 Control Flow and Pagination]] | 🔶 in progress | — |
| M7 | Memory, lanes, cache | ⬜ | — |
| M8 | Plugins | ⬜ | — |
| M9 | Secrets, history, docs, packaging | ⬜ | — |

## Exit criteria

| | Criterion | Met |
|---|---|---|
| M1 | `@a.body.items[?(price > 10)].id` evaluates; a bad path suggests a fix | ✅ |
| M2 | The graph finishes in critical-path time; Ctrl-C actually stops it | ✅ |
| M3 | A live region survives a worker pool writing underneath it | ✅ |
| M4 | `orders partial in.csv out.csv` runs 12 of 21 steps; a pruned producer fails at validate time | ✅ |
| M5 | Nested JSON → flattened CSV → Excel in one pipeline, with a schema assertion | ✅ |
| M6 | A 40-page cursor source fans out into a bounded `foreach`, reported as one progress line | 🔶 |
| M7 | Intermediates at 3× budget complete by spilling; a CPU-bound join lands in a process | ⬜ |
| M8 | SQLite → join with an API → write back, no config; an external plugin `pip install`s and works | ⬜ |
| M9 | A new user imports a shared workflow and finishes a paginated API → CSV run from the README in ten minutes | ⬜ |

## What is deliberately not done yet

- `use` — invoking another workflow. Raises a named error, not a silent no-op *(M8)*
- `state/` and `plugins_bundled/` — empty directories with budgets, not stubs
- Spill, the governor, lanes, and the cache *(M7)*
- Secrets, run history, `doctor`, completions, the wheel *(M9)*

## Gates, at every commit

`ruff check` · `ruff format --check` · `mypy` (strict) · `pytest` · `scripts/check_budget.py`

Currently: **517 tests**, 8,942 of 16,000 budgeted lines.
