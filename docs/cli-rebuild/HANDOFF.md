# SCLPL CLI Rebuild — Handoff

Pick up here. Read this file first, then **`SPEC.md`** — the normative implementation spec you build
from. `plan.html` is the full argument with evidence; read it when you need the reasoning behind a
constraint.

**`docs/vault/` is an Obsidian vault** covering how the thing works and why it is shaped that way —
open it as a vault, or read it as plain Markdown starting at `docs/vault/Start Here.md`. It is kept
current as the work goes: every major decision lands in `docs/vault/Decision Log.md`.

**All ten milestones are done (1 Sep 2026). §10 has what they left behind, and what is deliberately still open.**

---

## 1. Where the work lives

| | |
|---|---|
| Baseline commit | `1b1abe0` — full pre-rework tree (TUI + web studio), 369 files |
| Working branch | `worktree-cli-studio` (created under `.claude/worktrees/cli-studio`) |
| Original checkout | should be fast-forwarded back to `main` when this handoff is merged |
| Plan (why) | `docs/cli-rebuild/plan.html` |
| Spec (what to build) | `docs/cli-rebuild/SPEC.md` — normative |

The baseline commit is now the only copy of the Textual TUI and the Vue/FastAPI studio — M0 deleted
them from the working tree. Do not delete `main`.

---

## 2. What is being built

`sclpl` — a CLI-only pipeline runner for HTTP APIs. Reads a workflow (JSON or SCLPLL) by name or
path, resolves a dependency DAG, executes it as fast as the remote allows, writes CSV / JSON /
Parquet / Excel. No TUI, no web UI, no server.

Three audiences, one tool: an analyst runs and binds files; a data engineer authors workflows and
wires plugins; a software engineer implements functions, connectors, and operator overloads.

---

## 3. Why it is a rewrite and not a port

Four defects in the current engine each independently block a required feature. Verify them before
arguing with the plan — they are all still present at the baseline commit.

| # | Defect | Evidence | Blocks |
|---|---|---|---|
| 1 | Every value is stringified between steps | `app/core/models/context.py:24`, `app/core/engine/workflow.py:97`, `app/core/engine/variable_resolver.py:57` | Comparisons, arithmetic, sorting, dataframes |
| 2 | Scheduler runs in barrier waves, not continuously | `app/core/engine/parallel_workflow.py:60-66` | "Start the moment dependencies are ready" |
| 3 | New `AsyncClient` (and TCP connection) per request | `app/services/request_executor.py:33` | Throughput |
| 4 | Secrets silently fall back to base64 | `app/core/secrets.py:38-46` | Credential safety |

---

## 4. Invariants — do not break these

1. **stdout is data, stderr is interface.** Progress never touches stdout.
2. **Values keep their Python type end to end.** Stringify only at an interpolation boundary.
3. **The DAG is inferred from references.** A step that reads `@orders` depends on `orders`;
   dependency lists are never hand-maintained.
4. **One writer to the terminal.** Every worker, plugin, and log record emits an event to a single
   queue; exactly one task holds the stderr handle. This is what keeps the live region intact.
5. **The render ladder only descends** — `full` → `simple` → `plain`. Never climbs back up.
6. **Modes may only subtract steps and override scalars.** They can never add a step, change a
   dependency, or alter an expression.
7. **Expressions are evaluated over an allowlisted AST.** Never `eval()`.
8. **No abstraction until the second caller.** The old `contracts/` package had one implementation
   per interface; do not recreate it.
9. **Secrets never reach a log, a bar label, or a trace dump.** Redaction lives in the reporter.
10. **Reference docs are generated.** Hand-editing `docs/reference/` is a CI failure.

---

## 5. Size budget (checked in CI)

Target **16,000 checked lines** total, against ~59,000 deleted in M0.

| Package | Budget | | Package | Budget |
|---|---:|---|---|---:|
| `cli/` | 1,400 | | `expr/` | 1,500 |
| `render/` | 1,300 | | `expr/ops/` | 1,400 |
| `catalog/` | 500 | | `tables/` | 900 |
| `run/` | 3,600 | | `ext/` | 700 |
| `run/sclpll/` | 1,200 | | `state/` | 900 |
| `values/` | 1,000 | | `functions/` | 1,200 |
| `plugins_bundled/` | 600 | | | |

Dependencies, each doing three or four jobs: `httpx`, `typer`, `pydantic`, `aiosqlite`, `pyarrow`.
**`rich` is deliberately not a dependency** — the terminal layer is hand-written (see §7).

---

## 6. Milestones

Each is independently demonstrable. Do them in order; M0–M3 already produce a usable tool.

| | Milestone | Exit criterion |
|---|---|---|
| ~~**M0**~~ | ~~Strip and skeleton~~ | **Done.** `sclpl call GET https://httpbin.org/json` works and honours `-q` / `-v` / `--json` |
| **M1** | Typed values and expressions | `@a.body.items[?(price > 10)].id` evaluates; a bad path fails with a suggestion |
| **M2** | Scheduler and transport | The 7-node graph in plan §10 finishes in critical-path time; 500 steps share one pool; `Ctrl-C` is clean |
| **M3** | The view | pty snapshots pass at all three rungs; piping, resizing, and `Ctrl-C` each leave a restored terminal |
| **M4** | IR, catalogue, modes, launcher | `sclpl orders partial in.csv out.csv` runs 12 of 20 steps; pruning a needed producer fails at validate time; bare `sclpl` opens the menu |
| **M5** | Functions and tables | Nested JSON → flattened CSV → Excel in one pipeline, with a schema assertion |
| **M6** | Control flow and pagination | A 40-page cursor source fans out into a bounded `foreach`, reported as one progress line |
| **M7** | Memory, lanes, cache | Intermediates at 3× the memory budget complete by spilling; a CPU-bound join auto-lands in a process |
| **M8** | Plugins and the bundled set | SQLite → join with an API → write back, no config; an external plugin `pip install`s and works |
| **M9** | Secrets, history, packaging, docs | A new user imports a shared workflow and finishes a paginated API → CSV run from the README in ten minutes |

---

## 7. The two decisions most likely to be re-litigated

**Terminal rendering is hand-written, not Rich.** Reversed mid-planning on the owner's instruction
("rich breaks easily"). The live region must survive a worker pool writing underneath it, and a
breakage in a user's terminal is not reproducible. ~250 lines, single-writer discipline, a
descend-only fallback ladder, guaranteed restoration via `finally` + `atexit` + signal handlers,
byte-exact pty snapshot tests, and `--plain` / `SCLPL_RENDER` escape hatches. Cost accepted: we own
every terminal bug.

**SQLite ships as a bundled plugin, not as core.** It uses only the public plugin API, so it doubles
as proof the API is sufficient. Bundled set is `sqlite`, `fs`, `text`, `example`; everything else
installs on demand.

---

## 8. Decisions — all locked

Answered by the owner 21 Aug 2026. These are constraints now; changing one needs an ADR.

| # | Decision |
|---|---|
| 1 | Command is **`sclpl`**. No `sclplapi` alias. |
| 2 | Bare shorthand `sclpl orders partial in.csv out.csv` supported; explicit `sclpl run` required in scripts/CI. |
| 3 | pandas is the **`sclpl[data]` extra**. Missing extras are reported by **preflight**, which runs by default on every run (`--no-validate` opts out) — never mid-pipeline. |
| 4 | **SCLPLL v2, clean break, no v1 converter is built.** The four example workflows are rewritten by hand. |
| 5 | Run history in SQLite. **Retention configurable, default 5.** Runs are dated, named, taggable, searchable; pinned runs are exempt. |
| 6 | TUI / FastAPI / SPA **deleted outright in M0**. Baseline `1b1abe0` is the archive. |

Bare `sclpl` opens a numbered launcher (run saved, run by path, validate, history, import, rerun
last, environments, settings, help, exit). It prints the command it is about to run, appears only on
a TTY, and uses plain prompts — see `SPEC.md` §15.

Two further decisions made during planning, most likely to be re-litigated — see §7: the terminal
layer is hand-written (`rich` is not a dependency), and SQLite ships as a bundled plugin.

---

## 9. Current checkout drill

```bash
python -m pip install -e ".[dev]"
python -m pytest -q && python scripts/check_budget.py
python -m sclpl validate examples/orders.sclpll
```

All ten planned milestones are implemented. The current continuation work is integration hygiene:
run the gates, commit the worktree, merge it back to `main`, push `main`, and remove the temporary
worktree/branch so the repository has one active line again.

---

## 10. What M0–M9 left behind

**Deleted in M0: 250 files, 59,093 lines** — the Textual TUI, the FastAPI backend, the Vue SPA, and
the `app/` package they were entangled with. The whole of `app/` went, not just `app/ui/` and
`app/web/`: it was not separable (`services/` imported `app.web.errors`), and SPEC §4 describes the
tree with no `app/` in it. Carry-overs are at `docs/attic/carried/`; baseline `1b1abe0` is the
archive.

**Current checked state: 12,251 lines of code and 722 passing tests.** Gates are green.

| Milestone | Commit | What landed |
|---|---|---|
| M0 | `5a19bcc` | `render/` + `cli/` skeleton; the deletion |
| M1 | `f6c18da` | `values/`, `expr/` — typed values, the expression engine |
| M2 | `87a0a5a` | `run/{plan,schedule,retry,transport}.py` — continuous scheduling, pooled transport |
| M3 | `41d7745` | `render/live.py` — the live region |
| M4 | `773e747` | IR, both surfaces, catalogue, modes, ports, launcher |
| M5 | `86b9efa` | `tables/`, `functions/`, `ext/functions.py`, `bootstrap.py` |
| M6 | `f209f15` | five paginators, six control-flow kinds, measured bounds |
| M7 | `0da3229` | memory governor, lanes, cache |
| M8 | `505475c` | plugin ABI, bundled plugins, external scaffold |
| M9 | `39478b7` | secrets, history, doctor, completions, generated docs |

**What exists now**

| | |
|---|---|
| `sclpl/render/` | events + verbosity policy, single-writer reporter with redaction, capability probe and descend-only ladder, human/plain/jsonl sinks, the live region |
| `sclpl/cli/` | Typer root, global flags, `call`, `run`, `validate`, `explain`, `show`, `fmt`, `convert`, the catalogue commands, the bare launcher |
| `sclpl/values/`, `sclpl/expr/` | `ValueStore` with refcounts, path resolver with nearest-key suggestions, lexer/parser/AST, `(name, type)` dispatch with MRO walk-up |
| `sclpl/run/` | IR (pydantic, `extra="forbid"`), both surfaces, modes, ports, preflight, plan, scheduler, retry, transport, execute |
| `sclpl/tables/`, `sclpl/functions/`, `sclpl/ext/` | `Table` + backend protocol + pandas backend, format dispatch, the §10 flattening semantics, 43 built-ins, the `@function` registry |
| `sclpl/state/` | SQLite run history, tags, retention, pinned runs, NDJSON logs, secrets |
| `sclpl/plugins_bundled/` | `sqlite`, `fs`, `text`, `example`, all through the public plugin API |

**Five things to know now**

1. **`bootstrap.load()` is how anything gets registered.** Built-ins first, then plugins, so a
   plugin that shadows one is doing it deliberately. Tests that touch the catalogue call it; the CLI
   calls it once at import.
2. **Three names are owned by the catalogue, not by `expr/ops/`** — `join`, `flatten`, `merge`. Each
   means two things (a list into a string *and* two tables on a key; nested lists *and* nested
   objects), and the first argument is the same type either way, so the dispatch table cannot
   separate them. The implementations still live in `expr/ops/` as `join_text`, `flatten_lists`,
   `merge_objects`; the catalogue picks between them. Do not re-register any of the three.
3. **`tables/flatten.py:records_of()` is the single definition of "the records".** The writers and
   the function catalogue both call it, which is what stops `save_csv(@x)` and `flatten(@x)`
   disagreeing about what a row is. It reaches one level through `data`/`items`/`results`/
   `records`/`rows`.
4. **`@step name -> port` is how a writer gets its path.** The workflow says what it writes, the
   caller says where. Preflight checks the port is declared; `execute.py:_bind_output` supplies it,
   and a path written in the step still wins.
5. **The budget moved again, and got sharper.** ADR 0002 split `run/sclpll/` (a lexer, parser, and
   emitter, which grow with the grammar) out of `run/` (which grows with what the runner does).
   Totals are in SPEC §19. A third revision needs a better reason than the first two.

**Not done, deliberately:** `use` workflow invocation raises a named error rather than silently
doing nothing; Arrow IPC handoff to a process lane is still pickle-backed; lane assignment does not
yet learn from run history; `--http-cache` stores validators but does not yet perform revalidation
round trips; fan-out progress is correct but still row-per-iteration noisy for very large loops.
