---
tags:
  - milestone
---

# M6 Control Flow and Pagination

**Done.** Five paginators streaming into the scheduler, and every control-flow kind as a
runtime-injected subgraph.

## Exit criterion

> A paginated source fans out into a bounded `foreach`, reported as one progress line.

Met, and tested end to end through the real CLI
(`test_a_paginated_source_fans_out_into_a_bounded_loop`): a 30-item cursor source in
pages of 10, the first 8 fanned out at `concurrency 2`, `collect` keeping the ids.

The bound is **measured**, not assumed. Against a server that reports the peak number of
simultaneous requests it saw, 12 items with `concurrency 3` peaked at **3**; the same
workflow without the clause peaked at **9**. Global and host ceilings were 16 in both.
That is the whole argument for injection into the graph rather than a `gather` inside
the step. → [[Control Flow]]

## Pagination

All five strategies, verified against a mock serving 95 rows in 10-row pages: `cursor`,
`token`, `page`, `offset`, `link_header`. Every one returns all 95.

- `into`, `max_pages`, `stop_when`, and the caller's ceiling overriding the workflow's
- a **repeated request** ends paging, because an API that claims more and hands back the
  same page is a bug report rather than an infinite loop
- pages merge under the envelope key they arrived in, so `@fetch.body.data` means on
  page 40 what it meant on page 1
- `concurrent` is *reported* as ignored on the three sequential strategies
- preflight checks each paginate line has what its strategy needs

→ [[Pagination]]

## Control flow

`foreach`, `if`, `while`, `do_while`, `parallel`, `gate` — all six, all tested through
the real scheduler rather than by inspecting an expansion.

- `Scheduler.expand` grows the graph beneath a running node and moves that node's
  dependents to the barrier it creates
- `foreach` takes `concurrency` (a private per-tag ceiling) and `collect` (what an
  iteration contributes)
- `while` chains continuation nodes, one pass at a time; `do_while` skips the first check
- bodies run in written order within a copy, and never wait between copies

→ [[Control Flow]]

## What building it found

Six things, all in [[Decision Log]]:

1. **Nested body steps were plan nodes**, so any workflow with a `foreach` failed to
   compile at all — the parent claimed to produce them *and* they were their own specs.
2. **A body's references were not the parent's**, so a loop reading something from
   outside would have run before it existed. Invariant 3 held only for steps that
   happened not to be nested.
3. **Refcounts were fixed before expansion existed**, so a value read only by a loop body
   was freed the moment the parent settled. `ValueStore.retain` fixes it at injection.
4. **`parallel` and `gate` had no parser** and were being read as function calls.
   `otherwise` after a step landed inside that step's body as an unknown clause.
5. **`let "total {{@n}}"` produced the literal template** — the exact failure the rewrite
   exists to remove.
6. **A control step with an empty body** failed at runtime rather than at parse time,
   which is where the line number is.

## Not in this milestone

`use` — invoking another workflow — raises a named error pointing at M8, where it shares
a resolution path with the plugin and catalogue work. Not a silent no-op.
