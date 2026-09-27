---
tags:
  - concept
---

# Step Kinds

Eight things a step can be. `run/execute.py:_dispatch` matches on the config type; each
kind has one function.

## `http`

`run/execute.py:_http`. Interpolates the URL, headers, query, and body, then goes through
[[Transport|the pool]]. The result is always the same shape:

```python
{"status": 200, "ok": True, "headers": {...}, "body": <decoded>,
 "url": "...", "elapsed_ms": 12}
```

With `paginate`, two more fields appear — `pages` and `truncated` — and `body` is the
merged result. Without it the shape is byte-for-byte what it was, so `@fetch.body` means
the same thing either way. → [[Pagination]]

`extract` evaluates an expression against the response and produces that instead.

A URL that resolves to something without `://` is an error naming the template and the
values it interpolated, rather than a request to a malformed address.

## `fn`

`run/execute.py:_fn`. Resolves arguments, coerces them to the signature's types, and
calls through the [[Expressions#Dispatch|dispatch table]].

Two things it does that matter:

- **`-> port` binding.** A step declaring an output port gets the bound path appended if
  it did not supply one. A path written in the step still wins.
- **Error wrapping.** Anything that is not a `SclplError` is wrapped with the step id and
  the function name, because a bare `AttributeError` from inside a function names Python
  rather than the workflow.

## `let`

`run/execute.py:_let`. Binds the value of an expression. See
[[Expressions#The `let` template case]] for the one subtlety.

## `foreach` · `if` · `while` · `do_while` · `parallel` · `gate`

→ [[Control Flow]]

## `use`

`run/execute.py:_use`, with the work in `run/subflow.py`. Invoke another workflow as a
step: `use news_filter symbols=@watchlist days=1`.

Preflight resolves the workflow (like `sclpl run`, with the using file's directory
first) and checks it recursively: arguments name its `@input`s or `@var`s, required
inputs are given, its mode's closure check holds, and no chain of `use` loops back.

At runtime the child's kept steps are injected beneath the step as
`<step>::use::<child step>`, wired by the child's own plan -- the same expansion as a
[[Control Flow|foreach]] body, so every ceiling of the run applies. The child evaluates
against its own empty store and a parentless frame, so its names never meet the
parent's. The value is `{output: value}` for each declared output (a used workflow
returns its outputs rather than writing them), or its last step's value when it
declares none. Rationale: ADR 0016.

## Clauses every kind has

| Clause | Effect |
|---|---|
| `assert` | Expression checked against the result; failure exits 4 |
| `when` / `skip_if` | Expression checked first; true skips the step |
| `retry_if` | Expression deciding whether a failure is retryable |
| `retry` | Count and backoff |
| `tag` | Names a per-tag concurrency bucket |
| `lane` | Forces async / thread / process |
| `keep` | Exempt from disposal |

A step's own `assert` can see its own output: the frame binds both `result` and the
step's id.
