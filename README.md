# sclpl

A command-line pipeline runner for HTTP APIs.

`sclpl` reads a workflow, works out what depends on what from the references in it, runs
the graph as fast as the remote allows, and writes CSV, JSON, NDJSON, Parquet, Excel, or
SQLite.

No TUI, no web UI, no server, no accounts.

## Install

```bash
pip install sclpl
```

Extras: `[data]` for Excel and Parquet, `[keyring]` for OS-keyring secrets, `[crypto]`
for an encrypted secret file on a machine with no keyring.

```bash
sclpl doctor          # what is installed, and what any of it is missing
```

## Ten minutes, start to finish

### 1. One request

```bash
sclpl call GET https://api.example.com/orders | head
```

The body goes to **stdout** and the progress to **stderr**, so it pipes.

### 2. Make it a workflow

`orders.sclpll`:

```
@workflow orders "Every order, as a CSV"

@var base = "https://api.example.com"

@output report:csv

@step fetch
  get {{base}}/orders
  paginate cursor cursor_path=next_cursor param=cursor max_pages=40

@step write -> report
  save_csv @fetch.body
```

```bash
sclpl validate orders.sclpll      # no network, no writes
sclpl run orders.sclpll out.csv
```

That is the whole thing. `paginate` follows the source to its end and hands the merged
result on **with the same shape one page had**; `save_csv` flattens nested objects into
underscore columns and reaches through a `{"data": […]}` envelope without being told to.

### 3. Check it before you trust it

```
@step checked
  assert_rowcount @fetch.body.data min=1
```

An assertion failure exits **4**, not 1 — so a script can tell "the data was wrong" from
"the request failed".

### 4. Then

- **[Playbook 1](docs/playbooks/01-paginated-api-to-csv.md)** — this, in more detail
- **[Playbook 2](docs/playbooks/02-joining-sources.md)** — two sources, joined
- **[Playbook 3](docs/playbooks/03-automating.md)** — running it every night
- **[Playbook 4](docs/playbooks/04-debugging.md)** — when something is wrong
- **[Concepts](docs/concepts.md)** — every word this tool uses, in dependency order

## What it does that you might not expect

**The dependency graph is inferred.** Writing `@orders` in a step is what makes it wait
for `orders`. There is no `needs:` list to keep in sync, and none to fall out of date.

**Values keep their types.** A number stays a number the whole way through, so
`@a.total > 500` compares numbers and a table stays a table. Stringification happens only
at a `{{...}}` boundary you asked for.

**Steps start the moment their dependencies land**, not when a batch finishes. Two
fetches that do not reference each other run at once, without you arranging it.

**A run holding more than its memory budget spills to disk and finishes**, slower,
rather than being killed.

**A CPU-bound join moves to another process** on its own, decided by how big the data is
rather than by what the function is called.

**Secrets go in the OS keyring**, or an encrypted file. If neither is available, `sclpl`
refuses to store one rather than falling back to something weaker.

## The surface

```
sclpl run|validate|explain|fmt|convert    a workflow
sclpl call                                one request
sclpl import|list|show|remove             the catalogue
sclpl runs list|show|search|diff|replay|export|pin|prune
sclpl secret set|get|list|remove
sclpl plugin list|describe|scaffold|install
sclpl doctor|completion|docs build
```

Nothing is stubbed: if `--help` lists a command, that command works.

## Extending it

```bash
sclpl plugin scaffold mything
```

Writes a plugin that loads and runs immediately. Import from `sclpl.ext.api` and nothing
else — that module is the promise. SQLite and the filesystem connectors ship as bundled
plugins using exactly that API, which is how we know it is enough.

## Documentation

| | |
|---|---|
| [`docs/concepts.md`](docs/concepts.md) | The vocabulary |
| [`docs/playbooks/`](docs/playbooks/) | Four worked tasks |
| [`docs/reference/`](docs/reference/) | Generated from what is registered. Do not edit |
| [`docs/vault/`](docs/vault/) | An Obsidian vault: how it works and **why** it is shaped this way |
| [`docs/cli-rebuild/SPEC.md`](docs/cli-rebuild/SPEC.md) | Normative. Wins any disagreement |

## Developing

```bash
pip install -e ".[dev,data,crypto]"
python -m pytest -q
python scripts/check_budget.py      # per-package line budget
python scripts/check_layering.py    # no import cycles
python scripts/check_vault.py       # every wikilink resolves
sclpl docs build --check            # the reference is current
```

Six gates, all of which must pass before a commit: `ruff check`, `ruff format --check`,
`mypy` (strict), `pytest`, the budget check, and the layering check.

## Licence

See [`LICENSE`](LICENSE).
