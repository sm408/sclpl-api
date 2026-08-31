---
tags:
  - milestone
---

# M6 Control Flow and Pagination

**In progress.** #wip

## Goal

Five paginators streaming into the scheduler, and `foreach` / `if` / `while` /
`do_while` / `gate` / `parallel` as runtime-injected subgraphs.

**Exit:** a 40-page cursor source fans out into a bounded `foreach`, reported as one
progress line.

## Done

- ✅ **All five paginators** — `cursor`, `token`, `page`, `offset`, `link_header`.
  Verified against a mock serving 95 rows in 10-row pages; each strategy returns all 95.
  → [[Pagination]]
- ✅ **`into`, `max_pages`, `stop_when`**, the repeated-page guard, and the
  `HARD_CEILING`
- ✅ **Page merging** that keeps the shape one page had
- ✅ **`concurrent` reported as ignored** where it is impossible
- ✅ **Preflight validation** of paginate lines, replacing the "not followed yet" warning
- ✅ **`Scheduler.expand`** — the injection mechanism → [[The Scheduler#Runtime expansion]]
- ✅ **`foreach`, `if`, `parallel`, `gate`** — verified end to end
- ✅ **Nested bodies excluded from the plan**, references folded into the parent
- ✅ **`while` / `do_while`** parse and expand, with the continuation-node design
- ✅ **`-` as an output path** — so a paginated source can be piped

## Known gap, blocking

> [!bug] Refcounts are computed before expansion
> `Plan.readers_of` counts nodes that exist at plan time. An injected node's reads are
> not counted, so a value read **only** by a loop body is freed when the parent settles
> — and the body then fails with `nothing produces @start`.
>
> Reproduced by a `while` whose body reads a step outside the loop.
>
> Fix: `expand` must raise the refcount of anything the new nodes read, before those
> nodes can run. The store already has the machinery; the count just needs updating at
> injection time.

## Still to do

- [ ] The refcount fix above
- [ ] `foreach` `concurrency` — a per-loop ceiling below the global one
- [ ] `foreach` `collect` — an expression evaluated per iteration
- [ ] One progress line for a whole fan-out, rather than a row per iteration
- [ ] Rules blocks: `assert`, `skip_if`, `retry_if` as a block form
- [ ] Tests for all of the above
- [ ] The exit criterion, run for real

## Design notes

Everything about *why* the injection design is what it is lives in [[Control Flow]]. The
short version: a `gather` inside a step holds a worker and a semaphore slot while its
children run, so a hundred-element loop against a four-at-a-time host either deadlocks or
quietly exceeds its limit.
