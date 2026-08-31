---
tags:
  - milestone
---

# M7 Memory, Lanes, and Cache

**Done.**

## Exit criterion

> Intermediates at 3× budget complete by spilling; a CPU-bound join auto-lands in a
> process.

Both halves met, and both **measured** rather than asserted.

**Spilling.** Six 65 MB intermediates -- ~390 MB -- against a `--memory-budget 150M`.
The run completed, exit 0, with the right answer (360,000 rows). The log shows the
governor working:

```
warning: memory at 144.1MB of 150.0MB (96%); concurrency 16 -> 8
info: memory at 327.2MB of 400.0MB (82%); spilled 65.4MB to disk
```

**Lanes.** A `join` over 40,000 rows ran in PID 21772 while the parent was 20544. A
`join` over one row stayed on the event loop. Same function, different place, decided by
the size of the data.

## What landed

| | |
|---|---|
| `values/governor.py` | Watermarks, RSS sampling, spill selection, concurrency reduction |
| `run/lanes.py` | Assignment and execution across async / thread / process / serial |
| `values/cache.py` | Content-addressed blobs, a SQLite index, and all five flags |
| `Plan.release_points()` | Liveness over the pruned graph |
| `explain --memory` | Where each value is freed |
| `--memory-budget` | And four cache flags on `run` |

→ [[Memory and Spilling]], [[Lanes]], [[The Cache]]

## What building it found

**The Windows RSS probe fails silently.** `GetCurrentProcess()` returns the pseudo-handle
`0xFFFFFFFFFFFFFFFF`; without declared `argtypes` ctypes truncates it and the call
returns 0 -- which reads as "no memory in use", so the governor would never fire. Three
attempts to get right, and worth the note: a probe that fails loudly would have been
easier.

**`read_json` was about to be cached on its path.** Every `fn` step was cacheable, and a
reader's key is its arguments -- a *path*, not the file's contents. That would have
served yesterday's file from today's name, which is the worst kind of wrong because it
looks right. Readers and writers are both excluded now, for two different reasons.

**The governor reached for a global.** `sample()` called the module-level `rss()`, so
its policy could not be tested without a process that happened to be the right size. The
probe is injected now, which is also what lets a platform where it does not work supply
its own.

## Not in this milestone

- **Arrow IPC handoff.** A `Table` to a process is pickled, not shared zero-copy. Works,
  slower. #todo
- **History-based lane assignment.** Needs the run history from M9. #todo
- **HTTP revalidation.** `--http-cache` sets the policy and stores ETags; the 304 round
  trip itself is M9's, with the transport work it belongs to. #todo
