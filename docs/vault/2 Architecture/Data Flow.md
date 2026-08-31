---
tags:
  - architecture
---

# Data Flow

How a value travels, and what it is at each point. This note exists because
[[Invariants#2 Values keep their Python type]] is the invariant most easily broken by
accident.

```mermaid
flowchart LR
    R["HTTP response"] -->|decode| B["dict / list — real Python"]
    B --> S["ValueStore, by step name"]
    S -->|@ref| E["expression — still typed"]
    E --> F["function call — still typed"]
    F --> T["Table"]
    T --> W["file"]
    E -.->|"{{ }} only"| STR["str"]
```

## The one place a value becomes a string

`{{expr}}` inside a string literal. Nowhere else. `run/execute.py:_interpolate` is the
boundary, and `expr/eval.py:stringify` is the function that does it.

A bare `@ref` **outside** a string passes the object through untouched:

```
query limit={{page_size}}      # a string, because it is going into a URL
save_csv @fetch.body.data      # a list of dicts, because it is going into a table
```

## What the store holds

`values/store.py:ValueStore` maps a name to a `Value` with a refcount. The count comes
from `Plan.readers_of(name)` — how many nodes read it. When the last reader settles, the
value is freed and a `ValueFreed` event is emitted.

Two exceptions:

- **Leaves are pinned.** A node with no dependents is what the run produced; freeing it
  on arrival is not a memory saving.
- **Stubs are pinned.** A value standing in for a step the mode pruned has no producer,
  so its refcount would otherwise be wrong.

## Records, and what counts as one

`tables/flatten.py:records_of` is the single definition. It reaches one level through
the envelope keys `data`, `items`, `results`, `records`, `rows` — so `save_csv @fetch.body`
produces rows for `{"data": [...]}` rather than one very wide row.

Both the writers (`tables/io.py`) and the function catalogue (`functions/io_fns.py`) call
it, which is what stops them disagreeing. They used to. See [[Decision Log]].

## Flattening

Nested objects become underscore-joined columns. The rules are pinned in
[[Tables and Flattening]] and tested as reference behaviour, because a spreadsheet
formula depends on column order.
