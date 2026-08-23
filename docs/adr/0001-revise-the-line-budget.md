# ADR 0001 — Revise the line budget

**Date:** 23 Aug 2026
**Status:** accepted
**Supersedes:** the budget table in `SPEC.md` §19 and `HANDOFF.md` §5

## Context

SPEC §19 set a total budget of ~7,150 lines with a per-package table. Those numbers were
estimated before any of the code existed, from a plan document rather than from an
implementation. M1 was the first milestone to test them against real code, and two of
them were wrong by more than a rounding error:

| Package | Budget | Actual after M1 | Note |
|---|---:|---:|---|
| `expr/` | 800 | 1,922 | Includes `expr/ops/`, ten operator families |
| `render/` | 900 | 790 | Correct, but M3's live region is not written yet |

`expr/` is the clearest case. The 800 was meant to cover a lexer, a recursive-descent
parser, an AST, a path resolver, an evaluator, a dispatch table **and** the operator
catalogue that SPEC §4 places at `expr/ops/{compare,logic,arith,agg,string,coll,rel,
shape,temporal,cast}.py`. Ninety-odd operators, each with a docstring that becomes its
reference entry and an error message that says what to do instead, do not fit in what is
left after the machinery. The estimate did not undercount the implementation; it omitted
a whole category of file.

Projecting the same way for the milestones still to come — the scheduler and transport
in M2, the IR and SCLPLL surface in M4, the table layer in M5, plugins in M8, history
and secrets in M9 — the original total lands somewhere near half of what the specified
feature set requires.

## Decision

Re-derive the table from what each package demonstrably needs, rather than raise one
number at a time as each milestone hits the ceiling. Two changes of kind:

1. **`expr/ops/` gets its own budget.** It is a catalogue whose size tracks the language
   surface; `expr/` proper is machinery whose size should not track anything. Holding
   both to one number lets either hide growth in the other. `scripts/check_budget.py`
   now supports a `parent/child` key, counted separately and excluded from the parent.
2. **`plugins_bundled/` gets a budget.** It was omitted from §19 entirely, despite
   SPEC §11 specifying three bundled plugins.

| Package | Was | Now | | Package | Was | Now |
|---|---:|---:|---|---|---:|---:|
| `cli/` | 850 | 1,400 | | `expr/` | 800 | 1,300 |
| `render/` | 900 | 1,300 | | `expr/ops/` | — | 1,400 |
| `catalog/` | 400 | 500 | | `tables/` | 500 | 900 |
| `run/` | 1,400 | 3,200 | | `ext/` | 400 | 700 |
| `values/` | 600 | 1,000 | | `state/` | 400 | 900 |
| `functions/` | 900 | 1,200 | | `plugins_bundled/` | — | 600 |

**Total: 7,150 → 14,200.**

## Consequences

- The budget stays a CI gate and keeps doing its job. It is still the mechanism that
  makes unplanned growth visible; what changed is the baseline, once, from an estimate
  to a measurement.
- It is still measured against ~59,000 deleted lines. A finished `sclpl` at 14,200 lines
  replaces the previous tree at roughly a quarter of its size, which was the point of
  the number — not 7,150 specifically.
- Docstrings remain excluded from the count. Pricing explanation against implementation
  buys less of the thing that is harder to recover later.
- Any *further* revision needs its own ADR. This one is a correction of an estimate made
  without evidence; a second one would be a pattern, and the gate would stop meaning
  anything.
