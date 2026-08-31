---
tags:
  - concept
---

# Memory and Spilling

`values/governor.py`, and the spill machinery in `values/ref.py` it drives.

## The problem

A pipeline that holds three times its budget in intermediates should **finish, slower**,
by writing some of them to disk. What it should not do is die. An `OOMKilled` forty
minutes into a run costs the requests as well as the run, and says nothing about which
value was too big.

## Two watermarks

| | Fraction | What happens |
|---|---:|---|
| **soft** | 70% | Start spilling. Nothing is wrong yet; this is the point at which continuing to grow would make it wrong |
| **hard** | 85% | Halve the admission ceiling, and warn **with the numbers** |

```
warning: memory at 144.1MB of 150.0MB (96%); concurrency 16 -> 8
info: memory at 327.2MB of 400.0MB (82%); spilled 65.4MB to disk
```

"Memory pressure" is not actionable. A figure, a budget, and what was done about it are.

## The budget

`--memory-budget 4G`, or `@limits memory_budget=4G`, or **half the machine**. There is
always one: a governor that only exists when asked for is a governor that is missing
exactly when a run turns out bigger than expected.

Never below 512 MB, or the watermarks fire on an empty run.

## Measuring

Deliberately cheap and approximate. RSS is sampled (`/proc/self/statm`, `getrusage`, or
`GetProcessMemoryInfo`), and the store's byte counts are estimates. Both feed a decision
about whether to write a file, and that decision tolerates being wrong by a factor of
two. Being exact would cost more than the thing it protects.

`sample()` takes **the larger** of RSS and the store's own estimate. Each has a blind
spot — RSS includes the interpreter, the store misses everything it does not own — and
the maximum means neither can hide pressure.

A probe that cannot read anything returns 0, and a governor that cannot measure does
nothing. Spilling on a bad reading would make a healthy run slow for no reason.

> [!note] The Windows probe took three tries
> `GetCurrentProcess()` returns the pseudo-handle `0xFFFFFFFFFFFFFFFF`. Without declared
> `argtypes`, ctypes truncates it to a C int on the way out and then overflows on the
> way back in — and the call fails *silently*, returning 0, which reads as "no memory in
> use". Declaring the types is not optional.

## Spilling is not freeing

A spilled value is still there and still readable; it just lives on disk until something
asks for it. `ValueStore.get` resolves a `ValueRef` transparently, so no step and no
operator ever learns a value was spilled.

Largest first, and no further than needed. A hundred small files cost a hundred syscalls
to recover what one large one would.

Spilling stops as soon as the *estimate* says it is enough, rather than re-sampling RSS
each time. RSS does not fall until the allocator returns the pages, which it may not do
promptly, and waiting for it would spill everything.

## Formats

- A `Table` → **Parquet**: columnar, compressed, readable by anything
- Everything else → **pickle protocol 5** with out-of-band buffers, so a large binary
  payload is not copied on the way to the file

Below 64 KB nothing is spilled: the file, the syscalls, and the code path all cost more
than holding the object.

## Liveness

`Plan.release_points()` computes, over the **pruned** graph, the node after which
nothing reads each binding. Over the pruned graph on purpose: a partial run frees more,
because half the consumers are not there.

```bash
sclpl explain wf.sclpll --memory
```

```
  value                    read by  freed after
  ------------------------ -------- ------------------------
  block_a                  1        summed
  summed                   1        write
  write                    0        held (nothing reads it)
```

A leaf is held. "No consumer in the graph" is not the same as "nobody wants it", and
freeing the answer the moment it arrives is not a memory saving.

`--keep-all` disables disposal entirely. Debug mode leaves a **tombstone**, so a stale
read raises something naming the binding rather than a bare `KeyError` — which would
mean the liveness analysis and the actual reads disagree, a planner bug rather than a
user's.

→ [[The Value Store]], [[Lanes]], [[The Cache]]
