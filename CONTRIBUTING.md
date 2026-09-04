# Contributing to sclpl

Thanks for taking the time to improve `sclpl`. The project is intentionally small, local-first,
and strict about observable behaviour. Changes should preserve that character.

## Development setup

```bash
git clone https://github.com/sm408/sclpl-api.git
cd sclpl-api
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,data,crypto]"
```

## Before opening a pull request

Run the same checks used by CI:

```bash
python -m ruff check sclpl tests scripts
python -m ruff format --check sclpl tests scripts
python -m mypy
python -m pytest -q
python scripts/check_budget.py
python scripts/check_layering.py
python scripts/check_vault.py
sclpl docs build --check
```

## Engineering principles

- stdout is data; progress and diagnostics belong on stderr.
- Values keep their Python types until an explicit interpolation or output boundary.
- Workflow dependencies are inferred from references and must not be duplicated manually.
- Expressions use the allowlisted parser; never introduce `eval()` or `exec()`.
- Secrets must never appear in logs, labels, traces, fixtures, or snapshots.
- Generated files under `docs/reference/` are updated by `sclpl docs build`.
- Prefer a focused change with a regression test over a broad refactor.

## Pull requests

Describe the user-visible result, the design choice, and the verification performed. Include a
small workflow or fixture when a change affects the CLI, SCLPLL, plugins, or output formats.
Keep unrelated formatting and dependency changes out of the same pull request.

## Documentation

Record durable architectural decisions as numbered ADRs in `docs/adr/`. Keep the public guides,
examples, and generated reference in sync with behaviour. The Obsidian vault under `docs/vault/`
contains design rationale and historical context; the README and playbooks are the recommended
starting points for users.

