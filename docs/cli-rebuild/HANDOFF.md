# SCLPL CLI Rebuild — Handoff

Pick up here. Read this file first, then **`SPEC.md`** — the normative implementation spec you build
from. `plan.html` is the full argument with evidence; read it when you need the reasoning behind a
constraint. Nothing has been deleted yet — the rebuild starts at **M0**.

**All six open decisions were answered on 21 Aug 2026 (§8). M0 is unblocked.**

---

## 1. Where the work lives

| | |
|---|---|
| Baseline commit | `1b1abe0` — full pre-rework tree (TUI + web studio), 369 files |
| Working branch | `worktree-cli-studio` (created under `.claude/worktrees/cli-studio`) |
| Original checkout | sits on `feat/cli-studio`, still at the baseline |
| Plan (why) | `docs/cli-rebuild/plan.html` |
| Spec (what to build) | `docs/cli-rebuild/SPEC.md` — normative |

The baseline commit is the only copy of the Textual TUI and the Vue/FastAPI studio once M0 runs.
Do not delete `main`.

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

Target **~7,150 lines** total, against ~33,600 deleted.

| Package | Budget | | Package | Budget |
|---|---:|---|---|---:|
| `cli/` | 850 | | `expr/` | 800 |
| `render/` | 900 | | `tables/` | 500 |
| `catalog/` | 400 | | `ext/` | 400 |
| `run/` | 1,400 | | `state/` | 400 |
| `values/` | 600 | | `functions/` | 900 |

Dependencies, each doing three or four jobs: `httpx`, `typer`, `pydantic`, `aiosqlite`, `pyarrow`.
**`rich` is deliberately not a dependency** — the terminal layer is hand-written (see §7).

---

## 6. Milestones

Each is independently demonstrable. Do them in order; M0–M3 already produce a usable tool.

| | Milestone | Exit criterion |
|---|---|---|
| **M0** | Strip and skeleton | `sclpl call GET https://httpbin.org/json` works and honours `-q` / `-v` / `--json` |
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
as proof the API is sufficient — and it costs no new dependency because `aiosqlite` already carries
engine state and the cache index. Bundled set is `sqlite`, `fs`, `example`; everything else installs
on demand.

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

## 9. Start here

```bash
git log --oneline -1          # expect 1b1abe0 or later on worktree-cli-studio
```

Then M0, in this order:

1. Delete `app/ui/`, `app/web/`, `web/`, `tests/test_tui*.py`, `tests/test_web*.py`,
   `tests/test_*_api.py`. Move `docs/plan/` to `docs/attic/`.
2. Create the `sclpl/` package per plan §04. Keep `app/core/engine/sclpll_compiler.py` and
   `app/storage/` — they are the two pieces worth carrying over.
3. Stand up the Typer command tree and the reporter facade with all four sinks before any engine
   work, so every later milestone has somewhere to report to.
4. CI: ruff, mypy strict, pytest, and the line-budget check from §5.

Commit messages say what shrank. If a milestone adds a feature and the total drops, say so.
