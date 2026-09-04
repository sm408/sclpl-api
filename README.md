# sclpl

[![CI](https://github.com/sm408/sclpl-api/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/sm408/sclpl-api/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.13-3776AB)
![License](https://img.shields.io/badge/license-MIT-2f855a)

**A local-first command-line workflow runner for HTTP APIs.**

`sclpl` reads a workflow, infers the dependency graph from `@references`, runs the graph
as soon as each dependency is ready, and writes CSV, JSON, NDJSON, Parquet, Excel, or
SQLite outputs.

No server. No accounts. No web UI. Just workflows, Python values, and files you own.

---

## Why It Exists

Most API jobs start as one request and end as a brittle script. `sclpl` gives that middle
ground a shape: fetch pages, validate responses, join local data, transform records, keep
history, and export results without turning every workflow into a custom Python program.

| You need to... | `sclpl` gives you... |
|---|---|
| Pull every page from an API | Cursor, token, page, offset, and `Link:` pagination |
| Chain dependent requests | A graph inferred from `@step` references |
| Keep scripts pipeable | Response bodies on stdout, progress on stderr |
| Validate data, not just HTTP | Assertions with distinct exit codes |
| Work with tabular results | Flattening, joins, grouping, CSV, Excel, Parquet |
| Run safely at scale | Retries, cache, memory spilling, lane assignment |
| Extend the tool | Python functions and plugins through `sclpl.ext.api` |

## Install

```bash
pip install sclpl
```

Install extras for the parts you use:

| Extra | Adds |
|---|---|
| `sclpl[data]` | pandas-backed tables, Excel, Parquet |
| `sclpl[keyring]` | OS-keyring secret storage |
| `sclpl[crypto]` | encrypted-file secret storage for servers without keyrings |

Check the local environment:

```bash
sclpl doctor
```

## Ten-Minute Path

### 1. Send One Request

```bash
sclpl call GET https://api.example.com/orders | head
```

The body goes to **stdout** and progress goes to **stderr**, so `sclpl call` behaves like
a normal shell tool.

### 2. Turn It Into A Workflow

Create `orders.sclpll`:

```sclpll
@workflow orders "Every order, as a CSV"

@var base = "https://api.example.com"

@output report:csv

@step fetch
  get {{base}}/orders
  paginate cursor cursor_path=next_cursor param=cursor max_pages=40

@step write -> report
  save_csv @fetch.body
```

Validate without touching the network or filesystem:

```bash
sclpl validate orders.sclpll
```

Run it:

```bash
sclpl run orders.sclpll out.csv
```

`paginate` follows the source to its end and keeps the merged result in the same shape a
single page had. `save_csv` flattens nested objects into underscore columns and reaches
through a `{"data": [...]}` envelope without extra configuration.

### 3. Add A Data Check

```sclpll
@step checked
  assert_rowcount @fetch.body.data min=1
```

An assertion failure exits **4**, not 1. Automation can tell "the API failed" apart from
"the data was wrong."

## Command Surface

| Area | Commands |
|---|---|
| Workflows | `sclpl run`, `validate`, `explain`, `fmt`, `convert` |
| One request | `sclpl call` |
| Catalogue | `sclpl import`, `list`, `show`, `remove` |
| History | `sclpl runs list`, `show`, `search`, `diff`, `replay`, `export`, `pin`, `prune` |
| Secrets | `sclpl secret set`, `get`, `list`, `remove` |
| Plugins | `sclpl plugin list`, `describe`, `scaffold`, `install` |
| Admin | `sclpl doctor`, `completion`, `docs build` |

Nothing is stubbed: if `--help` lists a command, that command works.

## What Feels Different

**Dependencies are references.** Writing `@orders` in a step is what makes that step wait
for `orders`. There is no separate `needs:` list to maintain.

**Values keep their Python types.** A number stays a number, a table stays a table, and
stringification only happens inside `{{...}}` templates.

**The scheduler is continuous.** A ready step starts when its dependencies land, not when
some previous batch has finished.

**Large runs degrade deliberately.** When memory pressure rises, intermediates spill to
disk and concurrency is reduced before the operating system gets involved.

**Plugins use the public API.** Bundled `sqlite`, `fs`, `example`, and `text` plugins are
implemented through the same `sclpl.ext.api` surface external plugins use.

## Examples

Every workflow in [`examples/`](examples/) is validated by CI.

```bash
sclpl validate examples/orders.sclpll
sclpl validate examples/12-text-plugin-library.sclpll
sclpl run examples/playbook-01.sclpll out.csv --var base=https://api.example.com
```

Start with:

| Example | Shows |
|---|---|
| [`examples/orders.sclpll`](examples/orders.sclpll) | Modes, pagination, joins, reports |
| [`examples/playbook-01.sclpll`](examples/playbook-01.sclpll) | Paginated API to CSV |
| [`examples/playbook-02.sclpll`](examples/playbook-02.sclpll) | API rows joined with SQLite |
| [`examples/12-text-plugin-library.sclpll`](examples/12-text-plugin-library.sclpll) | Bundled text plugin helpers |

## Extending

Scaffold a plugin:

```bash
sclpl plugin scaffold mything
```

The generated plugin loads and runs immediately. Import from `sclpl.ext.api` and nothing
else; that module is the compatibility promise.

Add a built-in-style Python function with the function registry:

```python
from sclpl.ext.functions import function


@function("domain", builtin=False)
def domain(url: str) -> str:
    return url.split("//", 1)[-1].split("/", 1)[0]
```

## Documentation

| Path | Use it for |
|---|---|
| [`docs/playbooks/`](docs/playbooks/) | Worked tasks you can adapt |
| [`docs/concepts.md`](docs/concepts.md) | The vocabulary in dependency order |
| [`docs/reference/`](docs/reference/) | Generated command, function, expression, and plugin reference |
| [`docs/vault/`](docs/vault/) | Obsidian notes explaining why the system is shaped this way |
| [`docs/cli-rebuild/SPEC.md`](docs/cli-rebuild/SPEC.md) | Normative design spec; wins any disagreement |

Good next reads:

1. [`Paginated API to CSV`](docs/playbooks/01-paginated-api-to-csv.md)
2. [`Joining Sources`](docs/playbooks/02-joining-sources.md)
3. [`Concepts`](docs/concepts.md)
4. [`Functions Reference`](docs/reference/functions.md)

## Developing

```bash
pip install -e ".[dev,data,crypto]"
python -m ruff check
python -m ruff format --check
python -m mypy
python -m pytest -q
python scripts/check_budget.py
python scripts/check_layering.py
python scripts/check_vault.py
sclpl docs build --check
```

Before a commit, the required gates are lint, format, strict mypy, tests, line budget,
layering, vault links, and generated-doc drift.

## License

MIT, as declared in [`pyproject.toml`](pyproject.toml).
