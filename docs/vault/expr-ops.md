# `expr/ops/`

Budget 1,400. The operator catalogue — registrations, not machinery.

| File | Operators |
|---|---|
| `compare.py` | `eq` `ne` `lt` `le` `gt` `ge` `coalesce` `default` `is_null` `is_empty` |
| `arith.py` | `add` `sub` `mul` `div` `div_safe` `floordiv` `mod` `pow` `neg` `abs` `round` `ceil` `floor` `clamp` |
| `string.py` | `upper` `lower` `trim` `split` `replace` `matches` `extract` `extract_all` `starts_with` `ends_with` `pad_left` `pad_right` `slug` `text` `format` `url_encode` `json_encode` `json_parse` |
| `coll.py` | `count` `first` `last` `take` `drop` `chunk` `unique` `reverse` `sort` `contains` `contains_by` `pluck` `zip` `group_by` `entries` `keys` `values` `pick` `omit` `all` `any` and the aggregates `sum` `avg` `min` `max` `median` |
| `cast.py` | `number` `int` `bool` `list` `type_of` and the temporal set `now` `today` `date` `date_add` `date_diff` `date_format` `timestamp` |

Budgeted separately from [[expr]] because a catalogue grows with the language surface
while the machinery that reads it does not — [[The Line Budget]].

## Three names live elsewhere

`join_text` (in `string.py`), `flatten_lists` and `merge_objects` (in `coll.py`) are
defined here but **not registered**. The built-in catalogue owns those names, because
each covers two shapes the dispatch table cannot tell apart.

→ [[Expressions#Three names the catalogue owns]]

## Adding one

```python
@overload("upper", str, summary="Uppercase.")
def upper(value: str) -> str: ...
```

A typed overload beats a `@generic`. Reach for generic only when the type genuinely does
not matter. → [[Extending sclpl#An operator]]
