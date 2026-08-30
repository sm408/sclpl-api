# sclpl — working agreement

## What this is

`sclpl` is a **CLI-only** pipeline runner for HTTP APIs. It reads a workflow (JSON or SCLPLL v2) by
name or path, compiles it to a typed DAG, executes it with continuous dependency-driven scheduling,
and writes CSV / JSON / NDJSON / Parquet / Excel / SQLite.

**Non-goals: no TUI, no web UI, no server, no daemon, no accounts.** The Textual TUI and the
Vue/FastAPI studio were deleted in M0; commit `1b1abe0` is the archive.

## Read these first

| Document | Role |
|---|---|
| `docs/cli-rebuild/SPEC.md` | **Normative.** What to build. Wins any disagreement. |
| `docs/cli-rebuild/HANDOFF.md` | Where the work stands, and what to pick up next. |
| `docs/cli-rebuild/plan.html` | The argument and the evidence behind the constraints. |
| `docs/vault/` | **Obsidian vault.** How it works and why it is shaped this way. Start at `Start Here`. |

**Keep the vault current.** Every major decision gets an entry in `docs/vault/Decision Log.md`
in the same change that makes it — not later, and not only in a commit message. A commit
message is read once; a note is read when someone is about to undo the decision. The rules
are in `docs/vault/Maintaining This Vault.md`; `python scripts/check_vault.py` checks the links.

## Invariants — a violation is a review block, not a style note

1. **stdout is data, stderr is interface.** Progress never touches stdout.
2. **Values keep their Python type end to end.** Stringify only at an interpolation boundary.
3. **The DAG is inferred from references.** Reading `@orders` creates the dependency; dependency
   lists are never hand-maintained.
4. **One writer to the terminal.** Everything emits to a single queue; one task holds the handle.
5. **The render ladder only descends:** `full` → `simple` → `plain`. Never back up.
6. **Modes only subtract steps and override scalars.** Never add, never rewire.
7. **Expressions evaluate over an allowlisted AST.** Never `eval()` or `exec()`.
8. **No abstraction until the second caller.** The old `contracts/` package had one implementation
   per interface. Do not recreate it.
9. **Secrets never reach a log, a label, or a trace.** Redaction lives in the reporter.
10. **`docs/reference/` is generated.** Hand-editing it fails CI.

## Locked decisions

Changing one of these needs an ADR in `docs/adr/` recording date, reason, and migration impact.

1. The command is `sclpl`. No `sclplapi` alias.
2. Bare shorthand `sclpl <wf> [mode] [in…] [out…]` is supported; scripts and CI use `sclpl run`.
3. pandas and Excel ship as the `[data]` extra; missing extras are reported by preflight, never
   mid-run.
4. SCLPLL v2 is a clean break. No v1 converter.
5. Run history in SQLite, retention default 5, pinned runs exempt.
6. TUI / FastAPI / SPA are deleted, not deprecated.
7. **The terminal layer is hand-written. `rich` is not a dependency.** A live region must survive a
   worker pool writing underneath it, and a terminal bug in a user's shell is not reproducible.
8. SQLite ships as a bundled *plugin*, not core — which is how we know the plugin API is sufficient.

## Layout

`sclpl/` holds `cli/ render/ catalog/ run/ values/ expr/ tables/ ext/ state/ plugins_bundled/`.
The full tree, package by package, is SPEC §4.

## Rules of the road

- **Dependencies:** `httpx`, `typer`, `pydantic`, `aiosqlite`, `pyarrow`. Adding a sixth needs a
  reason in the commit message. Each existing one does three or four jobs.
- **Size budget:** per-package line budgets in SPEC §19, enforced by `scripts/check_budget.py` in
  CI. Deleting counts as progress; say what shrank in the commit message.
- **Gates:** `ruff check`, `ruff format --check`, `mypy` (strict), `pytest`, and the budget check.
  All five must pass before a commit.
- **Tests:** no network in CI except the local mock server in `tests/integration/conftest.py`.
  Secrets never appear in a fixture, a snapshot, or a log.
- **Nothing is stubbed.** If `--help` lists a command, that command works. A milestone registers its
  surface when it implements it.
