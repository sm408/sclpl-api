# 2. Budget the SCLPLL surface separately from the engine

- **Date:** 2026-08-31
- **Status:** accepted
- **Supersedes in part:** [0001 — Revise the line budget](0001-revise-the-line-budget.md)

## Context

ADR 0001 raised `run/` to 3,200 and closed by saying a further revision would need its
own ADR, because a budget revised twice without argument stops being a gate. This is
that argument.

At the end of M5, `run/` measures 3,254 — 54 over. The interesting part is where the
lines are:

| Under `run/` | Code lines |
|---|---:|
| `sclpll/parse.py` | 519 |
| `sclpll/emit.py` | 207 |
| `sclpll/lex.py` | 136 |
| **`sclpll/` total** | **866** |
| everything else (engine) | 2,388 |

`run/sclpll/` is not part of the execution engine. It is a lexer, a recursive-descent
parser, and a canonical emitter for a whitespace-significant language — a surface that
grows with the *grammar*, while `run/` proper grows with what the runner *does*. Holding
them to one number lets either hide growth in the other, which is exactly the failure
ADR 0001 identified when it split `expr/ops/` out of `expr/`.

So the 3,200 was not wrong about the engine. It was measuring two things at once.

## Decision

Split `run/sclpll/` into its own budgeted sub-package, and set the remaining numbers
against what M6 and M7 are known to add.

| Package | Was | Now | Why |
|---|---:|---:|---|
| `run/` | 3,200 | 3,600 | 2,388 today; M6 adds five paginators and control-flow expansion, M7 adds spill, the governor, and the cache |
| `run/sclpll/` | — | 1,200 | 866 today; M6 adds `foreach`/`while`/`rules` block syntax to all three files |
| `expr/` | 1,300 | 1,500 | 1,255 today, 45 left — too tight to absorb M6's filtered projections |

**Total: 14,200 → 16,000.**

The checker already supports `parent/child` keys, counting the child separately and
excluding it from the parent. No new mechanism was needed; the same one that separates
`expr/ops/` from `expr/` separates `run/sclpll/` from `run/`.

## Consequences

- The gate gets *sharper*, not slacker. Two numbers where there was one means grammar
  growth and engine growth are now visible separately, and neither can be spent on the
  other.
- 16,000 for a finished `sclpl` still replaces ~59,000 deleted lines at close to a
  quarter of the size, which is the comparison that motivated a budget at all.
- The `expr/` and `run/` raises are forecasts, not measurements, and forecasts are what
  ADR 0001 was written to distrust. They are deliberately modest: `run/` gets 1,212
  lines of headroom for two milestones' worth of named work, and `expr/` gets 245. If
  either proves short, that is evidence about the design, not a reason to raise it
  again.
- A third revision would need to explain why two corrections were not enough. The
  honest reading of that would be that the budget is being fitted to the code rather
  than the other way round.
