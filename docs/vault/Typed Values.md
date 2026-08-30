# Typed Values

[[Invariants#2 Values keep their Python type]], and where it is enforced.

## What the predecessor did

`app/core/models/context.py:24` stringified every value between steps. The consequences
compound:

- `@a.total > 500` compared `"500"` to `"500"` lexicographically
- arithmetic needed a cast at every use
- sorting was alphabetical, so `10` came before `9`
- a dataframe could not be passed anywhere

## What happens now

`run/transport.py:decode` turns a JSON response into real Python objects. From there the
value is stored, read, passed to functions, and written without conversion.

```python
# transport.py
if "json" in content_type:
    return response.json()   # dict / list / int / float / bool / None
```

A body that claims to be JSON and is not **raises**, rather than silently arriving as a
string — because a downstream `@a.body.items` would then fail somewhere much less
obvious.

## The boundary

One place converts: `expr/eval.py:stringify`, called from `run/execute.py:_interpolate`
when a string contains `{{`.

```
get {{base}}/orders           # base is interpolated → str, correct, it is a URL
query limit={{page_size}}     # 100 → "100", correct, it is a query parameter
save_csv @fetch.body.data     # stays list[dict], correct, it is going into a table
assert @fetch.status == 200   # int == int, not "200" == 200
```

## Where it can go wrong

Any new code path that builds a string from a value without going through
`_interpolate`. The review question is always: *does this value need to be text here, or
am I converting because it is convenient?*
