# ADR 0006 — Budget Batch D's transport completion

- **Date:** 2026-09-06
- **Status:** accepted
- **Amends:** [ADR 0005](0005-budget-test-manifest-package.md)

## Decision

`sclpl/run/`'s budget rises from 3,600 to 4,800 lines. The total source budget rises
from 19,800 to 21,000 lines.

Batch D (host/proxy policy completion, conditional HTTP caching, multipart and
streaming uploads/downloads, and extraction completeness signals) lands in
`run/transport.py`, `run/retry.py`, `run/execute.py`, and `run/paginate.py`. D1's
transport-service injection (`Clock`, injectable `now`/`sleep`/jitter) already used
the package's remaining 81 lines of headroom; the four D-batch tasks still ahead each
touch real protocol behavior -- Retry-After date/delta handling, proxy/TLS profiles,
ETag/Last-Modified revalidation and cache partitioning, bounded-memory streaming with
incremental checksums, and declared-scope/termination-reason pagination metadata --
and cannot reasonably fit in the space that remains.

## Consequences

`run`'s measured headroom returns to roughly 1,280 lines against the raised budget,
enough for the batch's remaining tasks without a second revision mid-batch. As with
ADR 0004/0005, this is an explicit, recorded expansion of one package's accounting,
not a bypass: `check_budget.py` still fails on any unbudgeted package or a total over
21,000 lines.
