# Workflow Anatomy

An SCLPLL file is a sequence of top-level directives followed by named steps. Blank lines and
comments beginning with `#` are ignored. Indentation is significant inside control-flow bodies.

```sclpll
@workflow orders "Fetch and export orders"

@var base = "https://api.example.com"
@output report:csv

@step fetch
  get {{base}}/orders
  query limit=100
  paginate cursor cursor_path=next_cursor param=cursor max_pages=40

@step checked
  assert_schema @fetch.body {"id": "integer", "total": "number"}

@step write -> report
  save_csv @checked
```

## What changes what

| Line or setting | Changes |
|---|---|
| `@workflow name` | The workflow identity used by the catalogue and run history |
| `@var name = value` | A value available to expressions and `{{...}}` templates |
| `@input name:format` | A file the caller must provide or bind |
| `@output name:format` | A file the workflow may write; the caller chooses its path |
| `@rule name = expression` | A reusable assertion or condition |
| `@limits ...` | Upper bounds for concurrency, timeout, retries, pages, and memory |
| `@mode name ...` | A validated subset of steps and scalar runtime overrides |
| `@step name` | A node and a typed value binding named `@name` |
| `@step a <- b` | Adds an explicit edge from `b` to `a`; references still add edges automatically |
| `@step write -> report` | Binds that step's writer to the caller's `report` output |
| `get/post/... URL` | Creates an HTTP step |
| `fn @value` or a named function call | Creates a function or plugin step |
| `let expression` | Creates a typed value without network or file I/O |
| `@name` | Reads a step, variable, input, or rule value and creates a dependency when applicable |
| `{{expression}}` | Interpolates an expression into a string, usually a URL or header |
| `paginate ...` | Repeats an HTTP step and merges the pages into one response |
| `retry ...` | Changes retry attempts and retryable statuses for that step |
| `cache ...` | Changes reuse policy for a step |
| `lane ...` | Overrides automatic event-loop, thread, process, or serial placement |
| `assert ...` | Rejects a step result with data-quality exit code `4` |
| `skip_if ...` | Skips a step when a condition is true |
| `tag ...` | Adds a label used by modes, limits, and run history |

## Values and dependencies

Every step binds its result under its id. In this example, `checked` depends on `fetch` because
it reads `@fetch.body`; no separate dependency list is required:

```sclpll
@step fetch
  get {{base}}/orders

@step checked
  assert_rowcount @fetch.body min=1
```

Bare references preserve their Python type. A list remains a list, a dictionary remains a
dictionary, and a table remains a table. Interpolation converts to text only inside a string:

```sclpll
@var base = "https://api.example.com"
@step request
  get {{base}}/orders
```

## HTTP steps

The first indented line determines the step kind. HTTP methods are `get`, `post`, `put`,
`patch`, `delete`, `head`, and `options`.

```sclpll
@step create
  post {{base}}/orders
  header Authorization: Bearer {{secret('api_token')}}
  header Content-Type: application/json
  query dry_run=false
  body {"customer_id": 42, "total": 120}
  timeout 20
  retry 3 on=[429, 500, 502, 503]
```

HTTP results have a stable shape: `status`, `ok`, `headers`, `body`, `url`, and `elapsed_ms`.
Paginated results additionally have `pages` and `truncated`.

## Function and plugin steps

Any registered built-in function or plugin connector can be used as the first line of a step:

```sclpll
@step shaped
  flatten @fetch.body

@step verified
  assert_schema @shaped {"id": "integer", "total": "number"}

@step labels
  text.template "{id}: {name}" @shaped
```

Arguments before `=` are positional; `name=value` arguments are keyword arguments. JSON objects,
lists, numbers, booleans, `null`, quoted strings, and references are supported.

## Ordinary Python scripts

Run a normal script directly, with its arguments unchanged. It runs with the same Python
environment as SCLPL, so `import sclpl` works without packaging the script as a plugin:

```bash
sclpl python scripts/report.py --month 2026-09
```

Use the built-in `python` function when that script belongs in a workflow. Its usual command-line
arguments stay ordinary arguments; `input=` sends a workflow value as JSON on standard input.
A JSON value printed to standard output becomes the step result, ready for the next step. Empty
output becomes `null`; other text output becomes a string. Write logs and diagnostics to stderr.

```sclpll
@step scored
  python "scripts/score.py" args=["--model", "v2"] input=@fetch.body

@step checked
  assert_rowcount @scored min=1
```

For example, `score.py` can remain a plain script:

```python
import json
import sys

rows = json.load(sys.stdin)
json.dump([{"id": row["id"], "score": 1} for row in rows], sys.stdout)
```

Scripts are trusted local code, like plugins: SCLPL does not sandbox them. Use a plugin only when
you need a reusable, named integration rather than a project-local script.

## Outputs

The workflow declares formats, while the caller supplies paths:

```sclpll
@output report:csv
@output profile:json

@step write_report -> report
  save_csv @rows

@step write_profile -> profile
  save_json @profile
```

Bind by position or by name:

```bash
python -m sclpl run workflow.sclpll report.csv profile.json
python -m sclpl run workflow.sclpll --out report=report.csv --out profile=profile.json
```

## Modes

A mode may subtract steps and override scalar limits. It may not add steps, rewire dependencies,
or alter expressions:

```sclpll
@mode smoke "One page and no report"
  include fetch checked
  limit max_pages=1
```

```bash
python -m sclpl validate workflow.sclpll --mode smoke
python -m sclpl run workflow.sclpll --mode smoke --out report=smoke.csv
```

Validation fails before execution if a kept step needs a producer that the mode removed.

## Control flow

Supported control-flow forms are `foreach`, `when`/`otherwise`, `while`, `do_while`, `gate`,
and `parallel`:

```sclpll
@step enriched
  foreach @rows as row
    concurrency 4
    collect {"id": @row.id, "score": @row.total * 10}
    step score
      let @row.total * 10
```

Use `explain` after adding control flow. The parent step expands the graph at runtime, and the
planner still enforces the workflow's concurrency ceiling.

## Safety and operating rules

- Put progress on stderr and data on stdout.
- Give network steps timeouts and bounded pagination.
- Store credentials with `sclpl secret`; do not commit them.
- Validate before running and use `--json` when another program consumes run events.
- Use `--offline` to require cache hits and avoid the network.
- Use `sclpl runs show`, `diff`, and `export` to inspect a completed run.
