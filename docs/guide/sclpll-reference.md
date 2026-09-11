# SCLPLL Reference

SCLPLL is the readable, whitespace-significant workflow format. Directives begin at column zero;
step bodies are indented by a consistent amount, conventionally two spaces.

## Top-level directives

### `@workflow`

```sclpll
@workflow NAME "optional description"
```

Defines the workflow identity. `NAME` is used by catalogue lookup and run history.

### `@version`

```sclpll
@version 1
```

Sets the workflow document version.

### `@var`

```sclpll
@var base = "https://api.example.com"
@var page_size = 100
```

Defines a value available to expressions. Values can be strings, numbers, booleans, null,
lists, objects, or expressions referencing earlier values.

### `@input` and `@output`

```sclpll
@input source:csv
@input optional:json?
@output report:csv
```

Formats are `csv`, `json`, `ndjson`, `parquet`, `xlsx`, `sqlite`, and `auto`. A trailing `?`
marks an input or output optional.

### `@rule`

```sclpll
@rule healthy = @fetch.status == 200
```

Defines a named expression for `assert`, `when`, `skip_if`, or `retry_if`.

### `@limits`

```sclpll
@limits concurrency=16 host_concurrency=6 timeout=30 retries=2 max_pages=40 memory_budget=2G
```

These are ceilings, not promises that the runner will always use the maximum. The governor and
remote responses may reduce concurrency.

### `@mode`

```sclpll
@mode smoke "A small verification run"
  include fetch checked
  exclude write
  limit max_pages=1
```

Modes support `all`, `include`, `exclude`, `extends`, `limit`, `vars`, and `stub`. Modes can only
remove work or override scalar settings.

## Step headers

```sclpll
@step NAME
@step NAME <- dependency_one dependency_two
@step NAME -> output_port
@step NAME <- dependency -> output_port
```

Step ids may contain letters, numbers, `_`, and `-`, but must start with a letter or `_`. A step
id is also the name of its output value.

## Step kinds

The first body line selects the kind:

| First line | Kind | Typical use |
|---|---|---|
| `get`, `post`, `put`, `patch`, `delete`, `head`, `options` | HTTP | Call an API |
| `let` | Binding | Compute or store a value |
| Registered function name | Function | Transform, validate, read, write, or run a Python script |
| `foreach` | Fan-out | Run a body for each item |
| `when` | Conditional | Choose a branch |
| `while`, `do_while` | Loop | Repeat a bounded body |
| `parallel` | Parallel branches | Express independent branches explicitly |
| `gate` | Barrier | Name a synchronization point |

## HTTP clauses

```sclpll
@step request
  get https://api.example.com/items
  header Accept: application/json
  query limit=100 active=true
  body {"enabled": true}
  auth profile_name
  timeout 15
  paginate cursor cursor_path=next param=cursor max_pages=20
```

`paginate` strategies are `cursor`, `token`, `page`, `offset`, and `link_header`.

## Common step clauses

```sclpll
@step fetch
  get https://api.example.com/items
  retry 3 on=[429, 500, 503]
  cache ttl=300 key="items"
  lane thread
  tag nightly external
  assert @result.ok
  skip_if @config.disabled
  retry_if @result.status == 429
  keep
```

`retry`, `cache`, `lane`, `tag`, `assert`, `skip_if`, `retry_if`, and `keep` can follow any
compatible step. `assert` failures use exit code `4`.

## Python scripts

The built-in `python` function runs a named manifest registration, never a workflow-supplied path
or URI. Registrations pin a local project file or provider URI with SHA-256. Its `args` reach the
script as ordinary command-line arguments. `input` is serialised as JSON to standard input; JSON
printed to standard output becomes the step value. Empty output becomes `null`, while non-JSON
output is kept as text. Put logs and diagnostics on standard error.

```sclpll
@step scored
  python "score" args=["--model", "v2"] input=@rows
```

Run a script outside a workflow with `sclpl python score --model v2`. Both paths use the active
SCLPL Python environment, so the script may import `sclpl`. Scripts are trusted code and are not
sandboxed; SCLPL nevertheless refuses unregistered aliases and digest mismatches.

## Expressions

Expressions support literals, references, paths, calls, interpolation, comparisons, arithmetic,
boolean logic, collections, and registered operators:

```sclpll
@step summary
  let {"count": count(@rows), "total": sum(@rows, by="amount")}

@step selected
  let @rows[?(amount > 100)].id
```

Paths use dot access, bracket access, wildcards, and predicates. Expressions are parsed by an
allowlisted evaluator; they are never passed to Python `eval()` or `exec()`.

## Comments and quoting

```sclpll
# This whole line is ignored.
@var label = "A value with spaces"
```

Use quotes for strings containing spaces or punctuation. JSON objects and arrays are single
arguments when passed to functions or clauses.

## Validation and conversion

```bash
python -m sclpl validate workflow.sclpll
python -m sclpl explain workflow.sclpll
python -m sclpl fmt workflow.sclpll
python -m sclpl convert workflow.sclpll workflow.json
```

The JSON surface represents the same workflow IR. Formatting and conversion are intended to be
stable and are covered by the project's tests.
