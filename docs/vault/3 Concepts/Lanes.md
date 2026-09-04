---
tags:
  - concept
---

# Lanes

`run/lanes.py`. Where a step actually runs.

Most work in `sclpl` is waiting on a socket, and the event loop is the right place for
that. Two kinds are not.

**Blocking work** — a synchronous library call, a large file read. On the loop it stalls
every other step, including ones whose responses have already arrived.

**CPU-bound work** — a join over a hundred thousand rows. A thread does not help: the
GIL means it is the same core. A process does.

## The four

| Lane | Where | For |
|---|---|---|
| `async` | the event loop | anything awaiting I/O, and anything small |
| `thread` | a thread pool | blocking calls that release the GIL |
| `process` | a process pool | CPU-bound work over a large payload |
| `serial` | inline, no await | when ordering matters more than throughput |

## How one is chosen

In order:

1. **An explicit `lane` on the step.** `lane process` wins over everything.
2. **`async def` stays on the loop**, whatever its arguments look like. It is already
   cooperative, and moving it to a thread would run an event loop inside a thread to no
   purpose.
3. **The size of its arguments.** Over 1 MB → process. Over 64 KB → thread. Below that →
   the loop.

### Why a size threshold

Sending a value to a process costs a serialisation and a copy, and for a small payload
that costs more than the work it moves. The threshold is what keeps `sort_by` over ten
rows on the event loop where it belongs.

Measured: a `join` over 40,000 rows lands in another process; a `join` over one row
stays on the loop. Same function, different place, decided by the data.

## Falling back is correct

A process pool that cannot be created — a container without `/dev/shm`, a sandbox that
refuses `fork` — or a payload that will not pickle, falls back to a thread with the
reason logged at `-vv`.

The lane is an **optimisation**. The answer does not depend on where it was computed,
only the time does. A run that fails because a closure would not pickle has lost
something real to save something that was only ever a preference.

A pool that *breaks* is discarded rather than retried: every future on it is already
broken, and one dead pool should not fail every step after it.

## Pools are lazy

Neither pool is created until something needs it. A workflow that never leaves the event
loop should not pay for a process pool — on Windows that is a fresh interpreter per
worker, which is not free.

Both are closed with the run. A lingering process pool keeps the interpreter alive after
the CLI has printed its summary.

## Not yet

**Arrow IPC handoff.** SPEC §12 wants a `Table` moved to a process over shared memory,
zero-copy, rather than pickled. Today it pickles, which works and is slower. #todo

**History-based assignment.** SPEC §12 also wants rolling-median statistics from past
runs to inform the choice. Run history exists now; no lane policy reads it yet. #todo

→ [[Memory and Spilling]], [[The Scheduler]]
