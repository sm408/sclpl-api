# ADR 0004 — Budget the contract package

- **Date:** 2026-09-05
- **Status:** accepted
- **Amends:** [ADR 0003](0003-unified-upgrade-format-and-budget-contract.md)

## Decision

The local contract evaluator and its candidate generator live in `sclpl/contracts/`.
The package receives an explicit 700-line budget. The repository-wide target increases
from 18,400 to 19,100 lines, and `scripts/check_budget.py` enforces both figures.

## Consequences

Contract logic is visible to the same architecture gate as the rest of the upgrade.
Future contract capabilities must fit the budget or amend this ADR with their reason,
measured size, and test coverage. The evaluator deliberately starts with local,
JSON-compatible inputs; remote contract resolution needs its own policy decision.
