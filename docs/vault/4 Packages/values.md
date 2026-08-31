---
tags:
  - package
---

# `values/`

Budget 1,000. What a run holds in memory, and what it does when that is too much.

| File | Job | State |
|---|---|---|
| `store.py` | `ValueStore`, `Value`, `Frame`, refcounts, release | ✅ |
| `ref.py` | `ValueRef` — spill and rehydrate; the reader registry | ✅ |
| `digest.py` | Content hashing, for the cache key | ✅ |
| `cache.py` | Content-addressed cache and index → [[The Cache]] | ✅ |
| `governor.py` | Resource watermarks → [[Memory and Spilling]] | ✅ |

→ [[The Value Store]]

## The layering rule

`values/` must not import `tables/`. It needs to read a spilled Parquet file and does it
through `register_reader`, which `tables/__init__.py` calls at import:

```python
# tables/__init__.py
register_reader("parquet", read_parquet_file)
```

The dependency points the right way and the capability still exists. Inverting it the
other way — `values/` importing `tables/` — would make the store depend on pandas being
installed, which is exactly what the `[data]` extra exists to avoid.
