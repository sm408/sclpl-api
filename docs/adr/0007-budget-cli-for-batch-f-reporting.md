# ADR 0007 — Budget `cli/` for Batch F's reporting and lineage commands

- **Date:** 2026-09-08
- **Status:** accepted
- **Amends:** [ADR 0006](0006-budget-batch-d-transport-completion.md)

## Decision

`sclpl/cli/`'s budget rises from 1,800 to 2,000 lines. The total source budget rises
from 21,000 to 21,200 lines.

F2 (`sclpl runs report`, and `runs diff`'s workflow/environment compatibility check)
already spent the package down to 8 lines of headroom. F3 (output lineage: an
`output-path lookup` command that resolves the producing run/digest and reports
ambiguity or later modification) and the rest of Batch F cannot fit in what remains.
The report/lineage rendering logic itself lives in `render/`, which still has real
headroom (97 lines before F3); only the thin Typer command wrappers count against
`cli/`, and even thin wrappers do not fit eight lines.

## Consequences

`cli`'s measured headroom returns to roughly 208 lines against the raised budget.
As with ADR 0004/0005/0006, this is an explicit, recorded expansion of one package's
accounting, not a bypass: `check_budget.py` still fails on any unbudgeted package or
a total over 21,200 lines.
