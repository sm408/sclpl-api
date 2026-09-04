---
tags:
  - guide
---

# Built-in Functions

43 built-ins, registered through `ext/functions.py` and listed by `sclpl fn list`.

## How registration works

```python
@function("save_csv", builtin=True)
def save_csv(data: Any, path: str, *, sep: str = "_") -> str:
    """Write records to CSV, flattening nested objects."""
```

**Type hints are load-bearing.** From the signature alone `ext/functions.py` derives:

- the JSON Schema, via pydantic's `TypeAdapter`
- the `--help` text and shell-completion values
- the **coercion** that lets `"10"` from a workflow file arrive as the `int` the function
  declared

That last one matters most. A workflow file is text; without coercion every numeric
argument would arrive as a string and every function would have to defend itself.

Coercion is a *convenience, not a gate*: a value the annotation refuses is passed through
so the call fails with its own error rather than a type complaint about something that
would have worked.

`version` participates in the cache key, so changing what a function computes
invalidates results from the old one rather than silently mixing them.

## Writing

| | |
|---|---|
| `save_csv(data, path, *, sep, explode, columns)` | The reference flattening |
| `save_json(data, path, *, indent)` | Keeps nesting |
| `save_ndjson(data, path)` | One object per line |
| `save_parquet(data, path)` | Columnar, typed |
| `save_excel(data, path, *, sheet)` | Workbook |
| `save(data, path)` | Format from the extension |

Every writer **returns the path it wrote**, so `@save.path` is available to a later step
— an upload, a notification, a checksum.

## Reading

`read_csv` · `read_json` · `read_ndjson` · `read_parquet` · `read_excel` · `read` ·
`glob_read(pattern, *, concat)` · `convert(source, target)`

A glob matching nothing mentions shell quoting, which is the usual cause.

## Shaping

| | |
|---|---|
| `flatten(data, *, sep, explode, columns, max_depth, depth)` | Objects → columns, or lists → one list |
| `explode(data, field)` | Each array element its own row |
| `normalize(data, *, sep)` | Flatten and align |
| `to_table(data)` | Records → `Table` |
| `infer_schema(data)` | The types the records imply |
| `cast_schema(data, schema)` | Coerce named columns |
| `select(data, *columns)` · `rename(data, mapping)` · `head(data, n)` | |

## Combining

| | |
|---|---|
| `join(left, right, on, *, how)` | Tables on a key — **or** a list into a string |
| `merge(first, *rest)` | Objects (later wins) or record sets (stacked) |
| `concat(first, *rest)` | End to end |
| `sort_by(data, by, *, descending)` | |
| `dedupe(data, *, by)` | |
| `group_agg(data, by, *, agg)` | `count sum min max avg first last` |
| `pivot(data, *, index, column, value)` | |

`join`, `merge`, and `flatten` each cover two shapes — see
[[Expressions#Three names the catalogue owns]].

## Diagnostics

| | |
|---|---|
| `assert_schema(data, schema, *, strict)` | Columns and types; exits **4** |
| `assert_rowcount(data, *, min, max, exactly)` | |
| `assert_unique(data, by)` | Shows the duplicates, not just a count |
| `assert_no_nulls(data, *columns)` | Reports per column |
| `profile(data)` | Rows, columns, types, null counts |
| `describe(data)` | Per-column statistics |
| `sample(data, n)` | Evenly spaced, **both ends included** |

Every assertion **returns the data unchanged**, so it can sit mid-pipeline:

```
save_excel(assert_schema(read_csv('out.csv'), {'id': 'integer'}), 'out.xlsx')
```

Two deliberate choices:

- An **extra** column is fine unless `strict`. An API adding a field should not break a
  workflow that ignores it.
- An integer column satisfies `number`, and anything satisfies `string`. Those widenings
  never lose information; the reverse does.
- `sample` includes the last row. The last row is where a truncated response or a bad
  final page shows up, so a sample that can never reach it is the wrong tool.
