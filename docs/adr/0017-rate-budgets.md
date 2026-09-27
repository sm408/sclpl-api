# ADR 0017 — Rate budgets in `@limits`

- **Date:** 2026-09-27
- **Status:** accepted
- **Issue:** [#8](https://github.com/sm408/sclpl-api/issues/8)
- **Amends:** [ADR 0015](0015-budget-cli-for-i5.md) (the total source budget)

## Context

`@limits` only capped concurrency. Public APIs publish their limits as requests per
time window (3 a second, 120 a minute, 5,000 a day), and with fast responses a
concurrency of 2 can still send 30 requests a second. Authors were adding `sleep`
steps or guessing a concurrency that happened to stay under the rate.

## Decision

`@limits` gains a repeatable `rate=` key:

```sclpll
@limits rate=api.example.com:3/s rate=api.example.com:120/m rate=tag:api:10/s
```

- A spec is `HOST:N/UNIT` or `tag:NAME:N/UNIT`, `N` a positive whole number and `UNIT`
  one of `s`, `m`, `h`, `d`. Hosts compare case-insensitively and carry no port. The IR
  and the JSON surface hold the same strings as a list (`"rate": [...]`), in the order
  written, so `sclpl fmt` and `convert` round-trip byte-identically. A malformed spec
  is a validation error that names the accepted forms.
- **Budgets count HTTP requests, not steps.** They are enforced in the transport
  (`run/rate.py`, used by `Pool.request` and `Pool.stream_to_file`) before every
  attempt, so a retry and every page of a paginated step spend a slot. A gate on the
  scheduler's nodes would let one paginated step send its forty pages at once, which
  would break exactly the promise the budget exists to make. A step's `tag`s select the
  tag budgets; the request URL's host selects the host budgets. A redirect hop that
  httpx follows inside one attempt is not counted separately.
- **A sliding-window log, not a refilling token bucket.** A bucket of capacity N
  refilling at N/W can spend 2N-1 inside one window (N at once, then N-1 more as they
  drip back). The log keeps the send times of each budget's last N requests and admits
  the next only once the oldest has left the window, so no window of length W ever
  holds more than N sends. The cost is N timestamps per budget.
- **All or nothing, in the fixed order.** A request needs room in every budget that
  applies: the host's, then each tag's in sorted order -- the order `_Gate` takes
  semaphores in. It takes one slot from each in a single step with no await in between,
  or takes none and sleeps until the slowest would allow it, then checks again. Nothing
  is held while waiting, so a budget cannot take part in a deadlock. The wait is an
  `asyncio` sleep: it occupies no thread or process lane. Like a node waiting on a tag
  semaphore, the node keeps the scheduler slots it already holds while it waits.
- **`Retry-After` closes the host.** A 429 carrying `Retry-After` stops every request to
  that host until the given time, not only the one that was told. It applies only to a
  host that has a budget of its own, so a workflow without `rate` behaves exactly as
  before.
- **Visible.** `Pool.stats()["rates"]` reports, per spec, its limit, window, slots
  remaining in the current window, and how many requests waited and for how long. A
  request that waited emits a `StepThrottled(id, budget, delay_s)` event, shown at `-v`
  and written to the NDJSON log as `step_throttled`.
- **Lifetime.** Budgets belong to the `Pool` that owns them: one run's requests share
  them, and a caller that reuses one pool across runs shares them across those runs.
  Time comes from the pool's injectable `Clock`, so tests are deterministic.

## Line budget

`sclpl/run/`'s budget rises from 5,000 to 5,200 lines and the total source budget by
the same 200 lines (26,720 to 26,920 on the lineage of ADR 0015). The feature is about
130 lines of `run` (the window log, IR validation, and the transport hook). With the
adaptive host-limit fix (#7) merged, `run` measured about 5,000 lines before this
change and 5,138 after it, so it cannot fit the old number; the remaining ~60 lines
are ordinary headroom, not a reservation. If another budget revision to the total
lands first, this one still adds 200 lines to whatever the total then is.

## Consequences

`rate` is a pure addition: no workflow without it changes behaviour, and no new
dependency is involved. Budgets are per process; they do not coordinate between two
`sclpl` processes calling the same API.
