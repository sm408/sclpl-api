---
tags:
  - concept
---

# The Value Store

`values/store.py`. Names to values, with refcounts.

## Refcounts

The initial count for a name is `Plan.readers_of(name)` — how many nodes read it. Each
reader's `release()` decrements; at zero the value is dropped and a `ValueFreed` event
is emitted so `-vv` can show it.

Two things are pinned and never freed by refcount:

**Leaves.** A node with no dependents is what the run produced. "No consumer in the
graph" is not the same as "nobody wants it", and freeing the answer the moment it
arrives is not a memory saving.

**Stubs.** A value standing in for a producer the mode pruned has no producing node, so
its refcount would be wrong from the start.

`--keep-all` disables freeing entirely, for debugging.

## Frames

A `Frame` is a scope of local names with a parent chain — `let` bindings, a loop
variable, and the element under test inside a filter predicate.

Frames exist so a loop body can bind `item` fifty times concurrently without fifty
entries in the global namespace. `run/control.py` gives each iteration its own frame,
which is how `@fetch` inside a loop body means *this* iteration's `fetch`.

Lookup order in `expr/eval.py:_lookup_ref` is **store first, then frame**.

`ValueStore.retain` raises a count while a run is going. Control flow adds nodes the
plan never saw -- a loop body is not a node until the loop knows how many copies it has
-- and those nodes read things too. Without it, a value read *only* by a loop body was
freed the moment the loop's parent settled. → [[Control Flow]]

## Spill

`values/ref.py` holds `ValueRef` — a value that has been written to disk and can come
back. The reader registry (`register_reader`) is how `tables/` teaches `values/` to read
Parquet **without `values/` importing `tables/`**, which would be a layering violation
in the wrong direction.

Spilling is driven by the governor. → [[Memory and Spilling]]
