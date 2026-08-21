# sclpl

A command-line pipeline runner for HTTP APIs.

`sclpl` reads a workflow, resolves a dependency graph from the references in it, runs the graph as
fast as the remote allows, and writes CSV, JSON, NDJSON, Parquet, Excel, or SQLite. No TUI, no web
UI, no server.

> **Status: M0 of a rewrite.** The command below works today. Workflows, the expression language,
> the scheduler, and the rest of the surface land in M1–M9 — see
> [`docs/cli-rebuild/SPEC.md`](docs/cli-rebuild/SPEC.md) §17 for the milestone list, and
> [`docs/cli-rebuild/HANDOFF.md`](docs/cli-rebuild/HANDOFF.md) to pick the work up.

## Install

```bash
pip install -e ".[dev]"
```

Extras: `[data]` for pandas and Excel, `[keyring]` for OS-keyring secrets, `[dev]` for the toolchain.

## Use

```bash
sclpl call GET https://httpbin.org/json      # body to stdout, progress to stderr
sclpl call GET https://api.test/v1/orders -H "Authorization: Bearer $TOKEN"
```

Because stdout carries only data, it pipes:

```bash
sclpl call GET https://httpbin.org/json | jq .slideshow.title
```

### Output control

| Flag | Effect |
|---|---|
| `-q` / `-qq` | Errors and summary only / total silence |
| `-v` … `-vvv` | Step lines, then timings and retries, then scheduler detail |
| `--json` | NDJSON events on stderr; the human view is suppressed |
| `--plain` | One line per event, no escape sequences |
| `--no-color` | Keep the layout, drop the colour (`NO_COLOR` does the same) |

`SCLPL_RENDER=plain|simple|full` overrides the auto-detected renderer.

### Exit codes

`0` success · `1` step failure · `2` usage · `3` validation · `4` assertion · `5` cache miss under
`--offline` · `6` unknown workflow or mode · `130` interrupted.

## Design

Ten invariants govern the code; they are listed in
[`docs/cli-rebuild/SPEC.md`](docs/cli-rebuild/SPEC.md) §3. The two that shape most of what you will
read:

- **stdout is data, stderr is interface.** Progress never touches stdout.
- **One writer to the terminal.** Every worker and plugin emits an event to a single queue; exactly
  one task holds the stderr handle.

The terminal layer is hand-written — `rich` is deliberately not a dependency. Dependencies are
`httpx`, `typer`, `pydantic`, `aiosqlite`, and `pyarrow`.

## Development

```bash
python -m ruff check sclpl tests scripts
python -m ruff format --check sclpl tests scripts
python -m mypy
python -m pytest -q
python scripts/check_budget.py      # per-package line budget, SPEC §19
```

All four run in CI. The budget check is a gate, not a report: exceeding it means deleting something
or moving the number in the SPEC on purpose.

## History

The Textual TUI and the Vue/FastAPI studio this replaces are archived at commit `1b1abe0`. Their
documentation, examples, and workflows are under `docs/attic/`.
