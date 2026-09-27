# ADR 0016: Governor CPU and event-loop-lag signals

**Status:** accepted (pending review of issue #9)

## Context

The governor (`sclpl/values/governor.py`) watched memory only. A run can saturate the
CPU -- a `foreach` over process-lane steps, or a neighbouring workload on a shared
machine -- and nothing reacted. A starved asyncio loop shows up as lag long before
memory moves.

## Decision

Add two optional pressure signals, configured in `@limits` and off unless set:

```sclpll
@limits cpu_soft=70% cpu_hard=90% loop_lag_soft=100ms loop_lag_hard=250ms
```

- **CPU** is system-wide CPU percent since the previous sample, read with `psutil`.
  System rather than process, because process-lane steps run in child processes and a
  neighbour starves us just as surely as our own work.
- **Loop lag** is how late a periodic `loop.call_at` timer (100 ms tick) fires. A read
  also counts a tick that is overdue but has not run yet, because the governor samples
  right after a node publishes, which is usually right after the blocking call returned.

Policy, in `Governor.pace`, sampled after each publish but at most once per 0.5 s window:

- the worst signal decides, once per sample (CPU hard and lag soft halves; it does not
  halve and then subtract one);
- **soft**: admit one fewer; **hard**: halve; never below 1;
- **clear** (every watched signal below its soft, or its hard if no soft is set): one
  step back up, until the configured/memory ceiling is reached again. Memory never
  recovers (a one-way ratchet); load does, because CPU and lag are transient and a run
  that tripped a threshold once should not stay slow forever. Climbing one step per
  window rather than jumping back avoids re-entering the pressure it just left;
- running steps always finish: the cap only gates the next admission (`Scheduler._take`).

The load cap is held on the governor (`Governor.cap`) and combined with the memory
ceiling as `min(cap, memory ceiling)`, so the two policies stay independent.

Every change is reported: a `LogRecord` (warning when lowering, info when recovering)
naming the signal, the measured value, the threshold, and `concurrency before -> after`;
each lowering also emits `ResourceWarning(kind="cpu"|"loop_lag", current, budget)` with
the value (percent or ms) and the threshold crossed. No new event type was added, so the
sinks and the SPEC event protocol are unchanged.

**psutil is an optional extra**, `pip install 'sclpl[monitor]'`. When CPU thresholds are
set and psutil is absent, the run logs one warning saying CPU is not watched and how to
fix it, and carries on; loop lag needs nothing extra. Failing the run instead would turn
a safety net into a new way to fail.

Thresholds are validated when the workflow is read: CPU is a percentage in (0, 100],
`70%` or `70`; lag requires a unit (`250ms`, `0.25s`), because a bare number reads as
seconds everywhere else in `@limits` and as milliseconds to anyone used to loop lag.

With no threshold set, `parse_load` returns None, `Governor.pace` returns nothing, no
timer is started, and `admits(ceiling) == ceiling`: behaviour is unchanged.

## Budget

`sclpl/values` goes from 1,000 to 1,100 lines (1,040 used after this change), and the
total source budget from 26,720 to 26,820. The signals, their parsing, and the loop timer
live next to the memory policy they extend; `run` takes only the wiring (about 25 lines).

That wiring no longer fits once #7 (adaptive host limits, which added a resizable host
gate) and #13 (recording interrupted runs) landed first: together `run` reached 5,046
lines against 5,000. `run` therefore goes from 5,000 to 5,100 and the total from 26,820
to 26,920. None of the three changes is removable, and splitting the scheduler's admission
logic out of `run` would be a larger change than this budget line is worth.

## Consequences

- The long-running runner can reuse `Governor.pace` / `Decision` to shed low-priority
  runs first; that is not part of this change.
- Readings are taken at step boundaries (after a publish), which is also the only point
  at which admission happens, so a run of very long steps is paced as often as it can be.
