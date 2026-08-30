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

Invoke another workflow as a step. Lands in M8 with the plugin and catalogue work it
shares a resolution path with. Today it raises a named error telling you to inline the
steps or run the two workflows in sequence — not a silent no-op. #todo

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
