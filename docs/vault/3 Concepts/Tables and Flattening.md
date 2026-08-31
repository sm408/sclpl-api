---
tags:
  - concept
---

# Tables and Flattening

`tables/`. The dataframe wrapper, the format dispatch, and the flattening rules.

## Why a wrapper

`tables/base.py:Table` wraps a backend frame behind `TableBackend`, a Protocol. pandas is
imported in exactly one file — `tables/pandas_backend.py`, and lazily even there.

This is one of the two abstractions that earned its keep under
[[Invariants#8 No abstraction until the second caller]]: it is what makes pandas an
*extra* rather than a dependency, so `pip install sclpl` stays small and
`sclpl[data]` adds the heavy half.

A missing extra raises `MissingExtra`, which preflight turns into a note naming the
exact `pip install` — **before the first request**, never at the write step after every
request has been paid for ([[Locked Decisions#3 pandas and Excel ship as the `[data]` extra]]).

## The reference flattening semantics

**`save_csv` is the reference behaviour** (SPEC §10). These rules are pinned tightly in
`tests/unit/test_tables.py` on purpose: column order and separator choices are what a
downstream spreadsheet formula depends on, so changing either is a breaking change.

| Rule | Example |
|---|---|
| Nested objects join with `_` | `{"customer": {"name": "Ada"}}` → `customer_name` |
| Column order is depth-first, first-seen | `id, customer_name, customer_address_city, …` |
| A list of scalars joins with `,` | `["rush", "gift"]` → `rush,gift` |
| A list of objects is JSON-encoded | `[{"sku": "a"}]` → `[{"sku": "a"}]` |
| An empty list becomes null | `[]` → *(empty cell)* |
| A collision is suffixed, never overwritten | `a_b` and `a.b` → `a_b`, `a_b_2` |
| Depth is bounded (`max_depth`, default 12) | beyond it, the name is unreadable anyway |

`rush,gift` is readable in a cell; `["rush", "gift"]` is not. Losing a column silently is
worse than an ugly name.

## Column policy

- `union` (default) — every record gets every column, missing ones null
- `intersection` — only columns every record has
- `first` — the shape of the first record

## `explode`

Turns each element of an array field into its own row.

```
[{"id": 1, "lines": [{"sku": "a"}, {"sku": "b"}]}]
→ [{"id": 1, "lines_sku": "a"}, {"id": 1, "lines_sku": "b"}]
```

Objects in the array become `field_key` columns; scalars stay under `field`. An **empty**
array keeps the row with the field cleared — dropping it would lose the parent record
with no explanation.

> Which of the two happened is settled *before* the rows are built. Otherwise a record
> with no elements adds an all-null `lines` column beside the `lines_sku` ones, in every
> output. That was a real bug; see [[Decision Log]].

## `records_of` — the single definition

`tables/flatten.py:records_of` decides what "the records" are for any value. It reaches
one level through `data`, `items`, `results`, `records`, `rows`.

Both the writers and the function catalogue call it. They used to disagree:
`io.write` treated `{"data": [...]}` as one wide row while `flatten()` reached through
it — the same payload, two answers.

## Formats

`tables/io.py` is the one place that knows what an extension means, so `read_csv`, a
bound port, and the spill path all agree.

| Extension | Format | Round trip keeps |
|---|---|---|
| `.csv` `.tsv` | csv | flattened columns |
| `.json` | json | **nesting** |
| `.ndjson` `.jsonl` | ndjson | **nesting**, one object per line |
| `.parquet` `.pq` | parquet | flattened columns, typed |
| `.xlsx` `.xls` | xlsx | flattened columns |
| `.db` `.sqlite` `.sqlite3` | sqlite | via the bundled plugin |

The JSON formats keep the nesting they were given; the tabular ones flatten, because a
column called `customer` holding an object is no use to anything.

`-` means stdout. It carries no extension, so the format must come from somewhere else —
`save_csv` supplies it, and so does a port declared `:csv`. Without one there is nothing
to infer from, and guessing JSON would be a silent choice about someone's data. A binary
format to a terminal is refused with the redirect spelled out.
