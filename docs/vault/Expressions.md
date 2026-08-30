# Expressions

`expr/`. One lexer, one parser, one dispatch table. Never `eval()` —
[[Invariants#7 Expressions evaluate over an allowlisted AST]].

## Infix is sugar

`a.total > 500` parses to `gt(a.total, 500)`. There is one evaluator, and operators and
functions are the same thing to it.

## Paths

`@step.body.data[0].email`, with:

| Form | Meaning |
|---|---|
| `.name` | attribute or key |
| `[0]` | index |
| `[*]` | projection — map over a list |
| `[?(pred)]` | filtered projection |
| `["odd key"]` | bracket access for keys that are not identifiers |

**A missing path is an error**, carrying the path, the value actually present, and the
nearest valid key. It must never return the literal `{{...}}` — the predecessor did, and
that is the source of requests to malformed URLs.

The nearest-key suggestion uses **Damerau-Levenshtein**, not plain Levenshtein, so a
transposition costs one edit. Ceilings: 1 if the shorter name is ≤4 characters, 2 if ≤8,
else 3. Plain Levenshtein suggested `id` for `pric`; Damerau-Levenshtein suggests
`price`.

## Interpolation

`{{expr}}` inside a string stringifies **at the boundary only**. A bare `@ref` outside a
string passes the typed object through. This is [[Invariants#2 Values keep their Python type]].

`parse_interpolated` also treats a string that is a bare leading `@` as an expression, so
`save_csv @rows` binds the list rather than the characters.

> [!note] The `let` template case
> `let "total: {{@n}}"` is a string *literal* to the expression parser — correctly, that
> is what it is. `run/execute.py:_let` therefore evaluates, and if the answer is a string
> still carrying `{{`, interpolates it. Without that second step a step would produce the
> characters `{{@n}}`, which is the exact failure the rewrite exists to remove.

## Dispatch

`expr/dispatch.py`. One dict keyed by `(name, type)`, resolved on the runtime type of the
first argument with an **MRO walk-up** — so an overload for `dict` also serves an
`OrderedDict`.

```python
@overload("filter", list)
def _(xs: list, where: Callable) -> list: ...

@generic("coalesce")            # any first argument
def _(*values): ...
```

A typed overload beats a generic. A missing overload is an error naming the type it was
given **and listing the types that are registered**, because "unsupported operand" tells
you nothing about what to do next.

Reaching for `@generic` because a typed overload is inconvenient is how a dispatch table
becomes a pile of `isinstance` checks.

## Three names the catalogue owns

`join`, `flatten`, and `merge` are **not** registered in `expr/ops/`. Each means two
things and the first argument is the same type either way, so the table cannot separate
them:

| Name | Shape A | Shape B | Told apart by |
|---|---|---|---|
| `join` | a list into a string | two tables on a key | the second argument |
| `flatten` | nested lists into one | nested objects into columns | what the list holds |
| `merge` | objects, later wins | record sets, stacked | whether they are dicts |

The implementations still live in `expr/ops/` as `join_text`, `flatten_lists`, and
`merge_objects`; the catalogue picks. **Do not re-register any of the three.**

→ [[Decision Log]]
