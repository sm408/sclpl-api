# ADR 0008 — Budget the remote-resource integration surface

- **Date:** 2026-09-09
- **Status:** accepted
- **Amends:** [ADR 0007](0007-budget-cli-for-batch-f-reporting.md)

## Decision

`sclpl/cli/`'s budget rises from 2,000 to 2,300 lines and `sclpl/run/`'s budget rises
from 4,800 to 5,000 lines. The total source budget rises from 21,200 to 21,700 lines.

The provider-agnostic remote-resource surface adds policy plumbing to `run` (cache,
offline, staging, generation publication, and binding lifecycle) and small but real
CLI entry points for resource inspection and remote workflow options. At the measured
head of the integration, `cli` is 2,074 lines and `run` is 4,823 lines, so the prior
caps reject already-tested behavior rather than constraining unplanned growth.

The increase leaves 226 CLI lines and 177 runner lines at that measurement. The limits
remain separate: resource command growth cannot silently consume runner capacity, and
the repository-wide check still rejects either package exceeding its recorded bound.

## Consequences

This is an explicit accounting change, not a CI bypass. `scripts/check_budget.py`
continues to enforce every package limit and the 21,700-line total. Future resource
features that exceed either headroom must simplify the implementation or amend this
decision with new measured evidence.
