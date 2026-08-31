---
tags:
  - decision
---

# The Line Budget

`scripts/check_budget.py`, enforced in CI. A per-package ceiling on **code** lines.

## Why a budget at all

`sclpl` replaces ~59,000 deleted lines. The number that matters is the ratio: a finished
tool at 16,000 lines is roughly a quarter the size of what it replaces, and that is only
true if something keeps score.

The gate makes unplanned growth **visible**. It does not prevent growth — it makes
growth a decision someone writes down.

## Current

| Package | Budget | | Package | Budget |
|---|---:|---|---|---:|
| `cli/` | 1,400 | | `expr/` | 1,500 |
| `render/` | 1,300 | | `expr/ops/` | 1,400 |
| `catalog/` | 500 | | `tables/` | 900 |
| `run/` | 3,600 | | `ext/` | 700 |
| `run/sclpll/` | 1,200 | | `state/` | 900 |
| `values/` | 1,000 | | `plugins_bundled/` | 600 |
| built-in functions | 1,200 | | **Total** | **16,000** |

## Two rules that make it honest

**Docstrings do not count.** Charging prose against the same budget as implementation
buys less of the thing that is harder to recover later. The rule is one function in
`scripts/check_budget.py`.

**A `parent/child` key is counted on its own and excluded from its parent.** `expr/ops/`
is a catalogue of operators that grows with the language surface; `expr/` is the
machinery that reads it. Same for `run/sclpll/` and `run/`. Holding either pair to one
number would let one hide growth in the other.

## Revisions

Two, both with ADRs, because a budget revised silently is not a gate.

- **ADR 0001** (23 Aug 2026): 7,150 → 14,200. The original was estimated before any code
  existed and omitted `expr/ops/` and `plugins_bundled/` entirely.
- **ADR 0002** (31 Aug 2026): 14,200 → 16,000, and `run/sclpll/` split out. The 3,200 for
  `run/` was not wrong about the engine; it was measuring the engine and a language
  implementation with one number.

A third revision would have to explain why two corrections were not enough. The honest
reading of that would be that the budget is being fitted to the code rather than the
other way round.

→ [[Decision Log]]
