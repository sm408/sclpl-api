# Workflow catalog

This is the copy-and-adapt reference for SCLPLL files. It covers every top-level directive,
step form, clause, and bundled or local plugin. The generated [functions](../reference/functions.md),
[expressions](../reference/expressions.md), and [plugins](../reference/plugins.md) pages are the
signature-level inventories; rebuild them with `sclpl docs build`.

## Complete, small workflow

```sclpll
@workflow customer-export "Fetch, check, and export customers"
@version 1
@description "A complete but deliberately small example"
@var base = "https://api.example.com"
@input overrides:json?
@output report:csv
@limits concurrency=8 host_concurrency=4 timeout=30 retries=2 max_pages=40 memory_budget=2G

@rule response_ok = @fetch.status == 200
@mode smoke "One page, no file output"
  include fetch checked
  limit max_pages=1

@step fetch
  get {{base}}/customers
  query active=true limit=100
  header Accept: application/json
  timeout 20
  paginate cursor cursor_path=next_cursor param=cursor max_pages=40
  retry 3 on=[429, 500, 502, 503]
  tag api customers
  assert response_ok

@step checked
  assert_rowcount @fetch.body.data min=1

@step write -> report
  save_csv @checked
  keep
```

```bash
python -m sclpl validate customer-export.sclpll
python -m sclpl run customer-export.sclpll --out report=customers.csv
python -m sclpl run customer-export.sclpll --mode smoke
```

## File rules and values

- Directives start at column zero with `@`; step and control-flow bodies are indented.
- Blank lines and `#` comments are ignored.
- Step IDs begin with a letter or `_`, then use letters, digits, `_`, or `-`.
- `@name` reads a variable, input, rule, or earlier step. A step reference creates a dependency.
- `{{expression}}` interpolates a value into text; bare references preserve their Python type.
- Values support JSON-like literals, references, paths, calls, comparisons, arithmetic, boolean
  logic, collections, and collection predicates.

```sclpll
@var region = "IN"
@step selected
  let @orders[?(country == @region)].id
@step request
  get https://api.example.com/orders/{{@selected[0]}}
```

## Top-level tags (directives)

| Directive | Purpose | Example |
|---|---|---|
| `@workflow NAME ["description"]` | Required identity for the catalogue and run history. | `@workflow nightly-orders "Export orders"` |
| `@version N` | Sets the document version; default `1`. | `@version 1` |
| `@description "text"` | Sets or replaces the workflow description. | `@description "Finance reporting"` |
| `@default_mode NAME` | Makes a declared mode the default. | `@default_mode smoke` |
| `@var NAME = VALUE` | Defines a reusable typed value. | `@var page_size = 100` |
| `@input NAME[:FORMAT][?]` | Declares a caller-supplied file; `?` is optional. | `@input source:csv` |
| `@output NAME[:FORMAT][?]` | Declares a caller-selected output path. | `@output report:parquet` |
| `@rule NAME = EXPRESSION` | Names a reusable condition. | `@rule healthy = @fetch.status == 200` |
| `@limits KEY=VALUE ...` | Sets workflow runtime ceilings. | `@limits concurrency=8 timeout=30` |
| `@mode NAME ...` | Declares a validated subset and overrides. | `@mode smoke "Fast check"` |
| `@step NAME ...` | Declares a DAG node, bound as `@NAME`. | `@step fetch` |

Formats are `csv`, `json`, `ndjson`, `parquet`, `xlsx`, `sqlite`, and `auto`. A workflow
declares a format while the caller supplies a path. Use named output bindings for multiple ports:

```sclpll
@input customers:csv
@output report:csv
@output audit:json?
```

```bash
python -m sclpl run workflow.sclpll --out report=report.csv --out audit=audit.json
```

## Modes and limits

Modes only remove work and override scalars; they cannot add steps, rewire the graph, or change
expressions. Selectors accept IDs, globs, and `tag:NAME`.

```sclpll
@mode base "Normal reporting"
  include fetch_* transform_* write
  exclude tag:slow
  var page_size=25
  limit max_pages=1 timeout=10

@mode smoke
  extends base
  include checked
  stub customers=[]

@mode full all
```

| Mode form | Meaning |
|---|---|
| `@mode NAME all` | Begin with every step. |
| `@mode NAME +selector -selector` | Inline include/exclude selectors. |
| `include selector ...` / `exclude selector ...` | Add or remove selected steps. |
| `extends NAME` | Start from another mode. |
| `describe "text"` | Set mode documentation. |
| `var NAME=VALUE` | Override a workflow variable. |
| `limit NAME=VALUE` | Override a scalar limit. |
| `stub NAME=VALUE` | Supply a value for a pruned producer. |

`@limits` accepts `concurrency`, `host_concurrency`, `timeout`, `retries`, `max_pages`, and
`memory_budget`. These are ceilings; the governor or remote service may run below them.

## Step headers and common clauses

```sclpll
@step transform
  flatten @fetch.body
@step ordered <- transform
  sort_by @transform by="created_at"
@step write -> report
  save_csv @ordered
@step export <- ordered -> report
  save_csv @ordered
```

`<-` adds explicit ordering edges; references infer edges automatically. `->` binds a writer to
one declared output port.

| Clause / tag | What it does | Example |
|---|---|---|
| `tag NAME ...` | Labels a step for modes, limits, and history. | `tag nightly external` |
| `assert EXPRESSION` | Fails with data-quality exit code `4` if false. | `assert count(@rows) > 0` |
| `skip_if EXPRESSION` or `when EXPRESSION` | Skips the step if true. | `skip_if @config.disabled` |
| `retry_if EXPRESSION` | Retries only if true. | `retry_if @result.status == 429` |
| `retry [MAX] [KEY=VALUE ...]` | Configures retries. | `retry 3 on=[429, 500, 503]` |
| `cache off` | Disables caching for this step. | `cache off` |
| `cache ttl=N key="text"` | Sets cache policy and optional stable key. | `cache ttl=300 key="customers"` |
| `lane async\|thread\|process\|serial` | Overrides inferred placement. | `lane thread` |
| `keep` | Retains the value after consumers finish. | `keep` |

## HTTP steps

The first line is `get`, `post`, `put`, `patch`, `delete`, `head`, or `options`. Results expose
`status`, `ok`, `headers`, `body`, `url`, and `elapsed_ms`; pagination adds `pages` and `truncated`.

```sclpll
@step create-order
  post https://api.example.com/orders
  header Authorization: Bearer {{secret('api_token')}}
  header Content-Type: application/json
  query dry_run=false
  body {"customer_id": 42, "total": 120}
  auth production
  timeout 20
  extract data.items
  paginate cursor cursor_path=next_cursor param=cursor max_pages=40
  proxy "http://proxy.internal:8080"
  verify true
  stream downloads/orders.json
  retry 3 on=[429, 500, 502, 503]
```

| HTTP clause | Purpose |
|---|---|
| `header Name: value` | Adds or replaces a request header. |
| `query key=value ...` | Adds query parameters. |
| `body VALUE` | Supplies a JSON-compatible request body. |
| `auth NAME` | Selects an authentication profile. |
| `timeout SECONDS` | Overrides request timeout. |
| `extract PATH` | Selects a response path as step result. |
| `paginate STRATEGY KEY=VALUE ...` | Repeats and merges requests; strategies are `cursor`, `token`, `page`, `offset`, `link_header`. |
| `proxy URL` | Routes through a proxy. |
| `verify true\|false` | Enables or disables TLS verification. |
| `stream PATH` | Streams the response to a file. |

Use bounded pagination and timeouts in production. `--offline` requires a cache hit and prevents
network access.

## Binding, functions, and control flow

### `let` and functions

Use `let` for an expression-only step. Any registered function or plugin connector may start a
step; positional arguments precede `key=value` arguments.

```sclpll
@step total
  let sum(@orders, by="total")
@step preferred
  filter_rows @orders "country" equals="IN"
@step summary
  let {"count": count(@preferred), "total": @total}
```

The generated [functions reference](../reference/functions.md) lists every built-in and plugin
signature; [expressions](../reference/expressions.md) lists every operator. Core building blocks:
`read_*`, `save_*`, `flatten`, `explode`, `normalize`, `join`, `group_agg`, `select`, `rename`,
`filter_rows`, `dedupe`, `sort_by`, `profile`, `assert_rowcount`, `assert_schema`,
`assert_unique`, and `secret`.

### Ordinary Python scripts

The `python` built-in runs a local Python source file without requiring a plugin. The optional
`args` list is forwarded as the script's command-line arguments. The optional `input` value is
sent as JSON on stdin. Parse JSON stdout as the result; empty stdout is `null`, and other stdout
is returned as text. Keep logs on stderr.

```sclpll
@step source
  let [{"id": 1, "amount": 12.5}]

@step scored
  python "examples/13-python-script.py" args=["--multiplier", "2"] input=@source

@step verified
  assert_schema @scored {"id": "integer", "score": "number"}
```

For a standalone invocation, use `sclpl python examples/13-python-script.py --multiplier 2`.
The script runs in the active SCLPL Python environment and can therefore `import sclpl` if it
needs supported library functionality. It is trusted local code, not a sandboxed extension. Use
a plugin when the integration needs reusable packaging, discovery, or declared capabilities.

### `foreach`

```sclpll
@step scores
  foreach @orders as order
    concurrency 4
    collect {"id": @order.id, "score": @order.total * 10}
    step score
      let @order.total * 10
```

Headers accepted: `foreach row in @rows`, `foreach @rows as row`, and `foreach @rows` (binds
`item`). Put `concurrency` and `collect` above the nested `step` entries.

### `when` / `otherwise`

```sclpll
@step choice
  when @fetch.ok
    step success
      let @fetch.body
  otherwise
    step failure
      let {"status": @fetch.status, "message": "request failed"}
```

### `while` and `do_while`

```sclpll
@step poll
  while @state.pending
    step refresh
      get https://api.example.com/jobs/{{@state.id}}

@step first-then-check
  do_while @state.pending
    step refresh-again
      get https://api.example.com/jobs/{{@state.id}}
```

### `parallel` and `gate`

```sclpll
@step gather
  parallel
    branch
      step customers
        get https://api.example.com/customers
    branch
      step products
        get https://api.example.com/products

@step ready
  gate "Customers and products are available"
```

`parallel` requires one or more `branch` blocks. `gate` names a synchronization point and may
also use common clauses such as `tag` and `keep`.

## Plugin catalog

Plugins are trusted Python code, not sandboxed. Discovery checks installed entry points, then
`./plugins/`, then `~/.sclpl/plugins/`. Duplicate names are reported. `--deny-capability` refuses
loading a plugin that declares the denied capability.

```bash
python -m sclpl plugin list
python -m sclpl plugin list --static
python -m sclpl plugin list --refused
python -m sclpl plugin describe sqlite
python -m sclpl plugin scaffold my_plugin
python -m sclpl plugin install some-package
python -m sclpl run workflow.sclpll --deny-capability network
```

| Plugin | Capabilities | Contributions | Workflow snippet |
|---|---|---|---|
| `text` | none | `text.slug`, `text.split`, `text.join`, `text.template`, `text.extract` | `text.template "{id}: {title}" @rows` |
| `fs` | `fs:read`, `fs:write` | `fs.glob`, `fs.stat`, `fs.exists`, `fs.copy`, `fs.move`, `fs.remove`, `fs.mkdir` | `fs.glob "data/*.csv" recursive=true` |
| `sqlite` | `fs:read`, `fs:write` | `sqlite.query`, `sqlite.exec`, `sqlite.write`, `sqlite.schema` | `sqlite.query "data.db" "select * from orders where id = ?" 42` |
| `example` | none | `greet`, `example.echo` | `example.echo @value times=2` |
| `azure_blob` | `network`, `secrets:read`, `subprocess` | `azblob` resource provider | `azblob://account/container/blob.json` |

### Text plugin

```sclpll
@step slug
  text.slug "Quarterly Revenue Report"
@step fields
  text.split "a, b, c" sep="," strip=true
@step label
  text.join @fields sep=" / "
@step rendered
  text.template "{id}: {title}" @rows
@step extracted
  text.extract @rows title "^(.+)$" into=label
```

### Filesystem plugin

```sclpll
@step matching
  fs.glob "incoming/*.csv" recursive=true
@step present
  fs.exists "incoming/orders.csv"
@step copied
  fs.copy "incoming/orders.csv" "archive/orders.csv" overwrite=false
@step metadata
  fs.stat @copied
@step directory
  fs.mkdir "archive/processed"
```

`fs.remove path directory=true` recursively removes a directory and refuses directories without
the explicit flag. `fs.copy` and `fs.move` run in the thread lane.

### SQLite plugin

```sclpll
@step saved
  sqlite.write @rows "data/report.db" "orders" mode=upsert key="id"
@step query
  sqlite.query "data/report.db" "select id, total from orders where total > ?" 100
@step changed
  sqlite.exec "data/report.db" "delete from orders where total = ?" 0
@step schema
  sqlite.schema "data/report.db" table="orders"
```

`sqlite.write` modes are `replace`, `append`, and `upsert`; `upsert` requires `key`. Query
parameters are bound positionally. Every SQLite connector uses the thread lane.

### Example plugin and plugin authoring

```sclpll
@step greeting
  greet "Ada" excited=true
@step repeated
  example.echo @greeting times=3
```

Scaffold a local plugin, keep `plugin.toml` beside `__init__.py`, and import only the public API:

```python
from typing import Any
from sclpl.ext.api import connector, function

@function("my_plugin_hello")
def hello(name: str) -> str:
    """Return a friendly greeting."""
    return f"Hello, {name}."

@connector("my_plugin.echo")
def echo(value: Any, *, times: int = 1) -> list[Any]:
    """Return the input repeatedly."""
    return [value] * times
```

```toml
[plugin]
name = "my_plugin"
version = "0.1.0"
api = "sclpl/1"
module = "my_plugin"
capabilities = []

[[function]]
name = "my_plugin_hello"
summary = "Return a friendly greeting."

[[connector]]
name = "my_plugin.echo"
summary = "Return the input repeatedly."
```

Manifest contribution kinds: `connector`, `function`, `verb`, `auth`, `paginator`, `backend`,
and `resource`. Capabilities: `network`, `fs:read`, `fs:write`, `secrets:read`, and `subprocess`.
The API must be `sclpl/1`; incompatible, malformed, denied, or failed plugins appear under
`sclpl plugin list --refused`.

### Azure Blob resource plugin

`azure_blob` is a separately packaged local plugin, not a bundled connector. It registers the
`azblob` resource provider and declares the elevated capabilities shown above. Install its package
in the active environment before using it, then inspect it with:

```bash
python -m sclpl plugin describe azure_blob
```

Do not place connection secrets in workflow files. Store them with `sclpl secret set` and use the
configured authentication or provider flow.

## Operating checklist

```bash
python -m sclpl fmt workflow.sclpll
python -m sclpl validate workflow.sclpll
python -m sclpl explain workflow.sclpll
python -m sclpl run workflow.sclpll --json --out report=report.csv
python -m sclpl runs list
python -m sclpl runs show RUN_ID
python -m sclpl runs diff RUN_ID OTHER_RUN_ID
python -m sclpl docs build --check
```

Validate before running. Use assertions for data quality, named outputs for multi-output files,
timeouts plus bounded pagination for network calls, and `sclpl secret` rather than literal
credentials. `use` is deliberately unavailable for sub-workflow invocation in this release; see
[known limitations](../limitations.md).
