---
tags:
  - milestone
---

# M5 Functions and Tables

Commit `86b9efa`. Tables, the built-in catalogue, and the output-port binding M4 owed.

## What landed

- `tables/` — `Table`, the `TableBackend` protocol, the pandas backend, format dispatch,
  and the §10 flattening semantics → [[Tables and Flattening]]
- `functions/` — 43 built-ins → [[Built-in Functions]]
- `ext/functions.py` — the `@function` registry, schema generation, argument coercion
- `bootstrap.py` — built-ins first, then plugins, so a plugin that shadows one is doing
  it deliberately

## The collision

`join`, `flatten`, and `merge` were each registered twice. `join` collided outright at
load. `flatten` was worse: `overload("flatten", list)` silently shadowed
record-flattening for exactly the input it is used on.

Resolution: the catalogue owns all three.
→ [[Expressions#Three names the catalogue owns]]

## What running the example found

The M4 exit criterion was verified by running `examples/orders.sclpll` against a live
server — and it found five things M4 had left:

1. **`@step name -> port` was in the grammar and in no code.** A bound output port could
   not reach a writer.
2. **`split_args` counted `{{` but not `{`**, so `rename @p {"a": "b"}` split on its
   spaces.
3. **`let` split on the first `=`**, taking `by=` out of `sum(@rows, by="total")`.
4. **Exploding an array of objects left a stray all-null column** beside the ones it made.
5. **A function raising anything but a `SclplError`** surfaced as a bare `AttributeError`
   with no step, no call, and no remedy.

All five are in [[Decision Log]]. The lesson is in the method: the exit criterion was
"runs 12 of 20 steps", and it was only *actually* checkable once M5's functions existed.
Checking it found bugs no unit test had.

## Exit criterion

Nested JSON → flattened CSV → Excel in one pipeline, with a schema assertion. Met:

```
save_excel(assert_schema(read_csv('out.csv'),
           {'id': 'integer', 'customer_name': 'string', 'total': 'number'}),
           'out.xlsx')
```
