---
tags:
  - guide
---

# Running and Debugging

## Commands

| Command | What it does |
|---|---|
| `sclpl call` | One HTTP request. Body to stdout, progress to stderr |
| `sclpl run` | Run a workflow by name or path |
| `sclpl validate` | Check without running. No network, no writes |
| `sclpl explain` | Show the execution plan |
| `sclpl fmt` | Rewrite in canonical form |
| `sclpl convert` | Between the JSON and SCLPLL surfaces |
| `sclpl python SCRIPT.py [ARGS...]` | Run an ordinary script in the active SCLPL Python environment |
| `sclpl import` / `list` / `show` / `remove` | The catalogue |

Bare shorthand `sclpl <wf> [mode] [in…] [out…]` works for typing. **Scripts and CI use
`sclpl run`** ([[Locked Decisions#2 Bare shorthand is supported]]).

## Flags worth knowing

```
-v -vv -vvv     more detail; -vvv logs every admission decision
-q -qq          errors and summary only; then silence
--json          NDJSON events on stderr, human view off
--plain         force the plain renderer
--dry-run       plan and validate, execute nothing
--keep-all      do not free intermediates
--keep-going    do not stop at the first failure
--var k=v       override a workflow variable
--in n=p / --out n=p   bind a port by name
```

Global flags go **before** the subcommand: `sclpl -vv run wf`, not `sclpl run wf -vv`.

## Reading the output

Progress is on **stderr**; data is on **stdout**
([[Invariants#1 stdout is data, stderr is interface]]). So this is safe:

```bash
sclpl run wf --out report=- 2>/dev/null | jq '.[0]'
sclpl run wf --json 2> events.ndjson
```

For a workflow `python` step, the child script follows the same boundary: JSON stdout becomes
the step value and stderr is its diagnostics. `input=@value` supplies JSON stdin; `args=[...]`
supplies normal command-line arguments.

## When something is wrong

**Start with `validate`.** It catches ports, modes, the graph, expressions, function
names, `-> port` targets, and paginator configuration — without a single request.

```bash
sclpl validate wf.sclpll -m partial
```

**Then `explain`.** It shows what the mode pruned, what each step waits for, the
critical path, and how many roots can start at once. A step running later than expected
usually has an edge you did not intend — often a reference you forgot was there.

**Then `-vv`.** It shows resolved values, freed bindings, and per-page progress.

## Common shapes

| Symptom | Usually |
|---|---|
| A step ran before its data existed | A reference the scanner did not see. Check `explain` |
| `nothing produces @x` | A typo — the suggestion is usually right |
| A CSV with one very wide row | The payload was an envelope; `records_of` should have reached in. Report it |
| Exit 4 | The data was wrong. The requests were fine |
| Exit 3 | Nothing ran. Fixing and re-running costs nothing |
| Only one page | Check the `paginate` line; `validate` catches a missing `cursor_path` or `size` |

## Testing

```bash
python -m pytest -q
python scripts/check_budget.py
python -m ruff check sclpl tests && python -m ruff format --check sclpl tests
python -m mypy sclpl
```

All five must pass before a commit. No network in CI except the local mock server in
`tests/integration/conftest.py`. Secrets never appear in a fixture, a snapshot, or a log.
