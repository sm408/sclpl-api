# sclpl — Implementation Specification

**Status:** approved, unstarted. All decisions locked (§2). Work begins at M0 (§17).
**Companion documents:** `plan.html` (why, with evidence), `HANDOFF.md` (operational summary).
**Audience:** the engineer or agent implementing this. This document is normative — where it and
`plan.html` disagree, this one wins.

---

## 1. Product definition

`sclpl` is a command-line pipeline runner for HTTP APIs. It reads a workflow (JSON or SCLPLL v2) by
registered name or file path, compiles it to a typed DAG, executes it with continuous
dependency-driven scheduling, and writes results to CSV, JSON, NDJSON, Parquet, Excel, or SQLite.

**Non-goals.** No TUI. No web UI. No server, daemon, or scheduler. No accounts, no multi-user, no
remote state. No plugin sandbox — plugins are trusted code, gated by declared capabilities only.

**Three audiences.** Tier 1 runs and binds files. Tier 2 authors workflows and wires plugins.
Tier 3 implements functions, connectors, and operator overloads. Every capability is reachable at
all three levels; you descend only when you need to.

---

## 2. Locked decisions

| # | Decision | Consequence |
|---|---|---|
| 1 | Command is `sclpl`. No `sclplapi` alias. | One name in docs, completions, and error messages |
| 2 | Bare shorthand `sclpl <wf> [mode] [in…] [out…]` is supported | Explicit `sclpl run` required in scripts/CI |
| 3 | pandas/pyarrow ship as the `sclpl[data]` extra | Missing extra reported by preflight, never mid-run |
| 4 | SCLPLL v2, clean break, **no v1 converter** | The 4 example workflows are rewritten by hand |
| 5 | Run history in SQLite, retention default **5**, searchable | Also feeds lane auto-tuning |
| 6 | TUI / FastAPI / SPA deleted outright in M0 | Baseline commit `1b1abe0` is the archive |
| 7 | Terminal layer hand-written; **`rich` is not a dependency** | We own every terminal bug; see §14 |
| 8 | SQLite ships as a bundled *plugin*, not core | Proves the plugin API is sufficient; no new dep |

Changing any of these requires an ADR in `docs/adr/` recording date, reason, and migration impact.

---

## 3. Invariants

Violating one of these is a review block, not a style note.

1. **stdout is data, stderr is interface.** Progress never touches stdout.
2. **Values keep their Python type end to end.** Stringify only at an interpolation boundary.
3. **The DAG is inferred from references.** Reading `@orders` creates the dependency.
4. **One writer to the terminal.** All output flows through a single queue owned by one task.
5. **The render ladder only descends.** `full` → `simple` → `plain`, never back up.
6. **Modes only subtract steps and override scalars.** Never add, never rewire.
7. **Expressions evaluate over an allowlisted AST.** Never `eval()`/`exec()`.
8. **No abstraction until the second caller.**
9. **Secrets never reach a log, label, or trace.** Redaction lives in the reporter.
10. **`docs/reference/` is generated.** Hand-edits fail CI.

---

## 4. Repository layout after M0

```
sclpl/
  __main__.py            python -m sclpl
  cli/
    app.py               typer.Typer root; subcommand registration
    run.py               run, validate, explain, fmt, convert, call
    catalog_cmd.py       import {workflow,function,plugin,settings}, list, show, remove
    runs_cmd.py          runs list|show|search|diff|replay|export|pin|prune
    admin_cmd.py         env, secret, fn, plugin, cache, data, doctor, completion
    launcher.py          bare-invocation menu (§15)
    options.py           shared option types, config precedence resolution
  render/
    events.py            event dataclasses — the reporter protocol
    reporter.py          Reporter protocol + fan-out
    term.py              ANSI primitives, capability probe, restore
    human.py             full + simple rungs (live region)
    plain.py             plain rung
    jsonl.py             NDJSON sink
    redact.py            secret redaction filter
  catalog/
    store.py             registry files + SQLite index, versioning
    resolve.py           name|path -> WorkflowDoc
  run/
    ir.py                pydantic IR models
    compile_json.py      JSON surface -> IR
    sclpll/lex.py parse.py emit.py    SCLPLL v2 surface <-> IR
    modes.py             mode resolution, pruning, closure check
    ports.py             input/output declaration + binding
    plan.py              DAG, critical path, liveness, lane assignment
    schedule.py          ready queue, semaphores, workers
    steps/http.py fn.py control.py connector.py
    paginate.py          5 built-in strategies
    retry.py             backoff + jitter + Retry-After
    errors.py            typed diagnostics
  values/
    store.py             ValueStore, refcounts, release
    ref.py               ValueRef, spill, rehydrate
    digest.py            content hashing
    cache.py             content-addressed cache + index
    governor.py          resource watermarks
  expr/
    lex.py parse.py ast.py
    path.py              @ref path resolution
    dispatch.py          operator table + overloads
    ops/{compare,logic,arith,agg,string,coll,rel,shape,temporal,cast}.py
  tables/
    base.py              Table wrapper + TableBackend protocol
    pandas_backend.py
    io.py                read_*/save_* dispatch by extension
    flatten.py           nested JSON -> underscore columns
  ext/
    functions.py         @function registry
    plugins.py           discovery, manifest, ABI, capabilities
    scaffold/            plugin template
  state/
    db.py                aiosqlite connection + migrations
    history.py           run records, search, retention
    settings.py          config load/merge/show
    secrets.py           keyring-first, encrypted-file fallback
  plugins_bundled/
    sqlite/  fs/  example/
tests/
  unit/  integration/  pty/  golden/
docs/
  playbooks/  reference/  adr/  concepts.md
examples/
```

**Carried over from the old tree (the only two):** `app/core/engine/sclpll_compiler.py` as the
starting point for `run/sclpll/`, and `app/storage/` patterns for `state/db.py`. Everything else is
new; everything in §16 is deleted.

---

## 5. Core data model

```python
# values/store.py
Value = Any                       # a real Python object: int, str, dict, list, Table, bytes…

@dataclass(slots=True)
class Binding:
    """One named value produced by one step."""
    name: str                     # step id, or a `let` name
    value: Value | ValueRef
    digest: str                   # blake2b of canonical form; cache + rerun detection
    readers: int                  # remaining unread consumers; 0 => release
    pinned: bool = False          # output port or explicit `keep`

class ValueStore:
    def put(self, name: str, value: Value, readers: int, *, pinned: bool = False) -> None: ...
    def get(self, name: str) -> Value: ...          # rehydrates a ValueRef transparently
    def release(self, name: str) -> None: ...       # decrement; free + delete spill at zero
    def pin(self, name: str) -> None: ...
    def stats(self) -> StoreStats: ...
```

`ValueRef` holds a scratch path plus a rehydrator. Tables spill to Parquet, everything else to
pickle protocol 5 with out-of-band buffers. Rehydration is lazy and memoised for the lifetime of the
binding.

`ExecutionContext` from the old codebase is **deleted**. Steps receive typed arguments; there is no
shared mutable dictionary.

---

## 6. Workflow IR

The IR is canonical. JSON and SCLPLL are surfaces over it; `sclpl fmt` then `sclpl convert` must
round-trip byte-identically in both directions (property test, M4).

```python
# run/ir.py  — pydantic v2 models; these generate docs/reference/workflow-schema.md
class WorkflowDoc(BaseModel):
    name: str
    version: int = 1
    description: str = ""
    vars: dict[str, Expr | JsonValue] = {}
    rules: dict[str, Expr] = {}
    inputs: list[Port] = []
    outputs: list[Port] = []
    modes: dict[str, ModeSpec] = {}
    default_mode: str | None = None
    limits: Limits = Limits()
    steps: list[Step]

class Port(BaseModel):
    name: str
    format: Literal["csv","json","ndjson","parquet","xlsx","sqlite","auto"] = "auto"
    required: bool = True

class ModeSpec(BaseModel):
    all: bool = False
    include: list[str] = []        # step ids, globs, or "tag:name"
    exclude: list[str] = []
    extends: str | None = None
    vars: dict[str, JsonValue] = {}
    limit: dict[str, JsonValue] = {}   # e.g. {"max_pages": 1}
    stub: dict[str, JsonValue] = {}    # satisfy a pruned producer

class Step(BaseModel):
    id: str
    tags: list[str] = []
    needs: list[str] = []          # explicit; union'd with refs discovered in expressions
    kind: StepKind                 # http | fn | use | let | foreach | if | while | do_while | gate | parallel
    config: StepConfig             # discriminated union on kind
    assert_: str | None = None     # rule name or inline expression
    skip_if: str | None = None
    retry_if: str | None = None
    retry: Retry = Retry()
    cache: CacheSpec = CacheSpec()
    lane: Literal["async","thread","process","serial"] | None = None   # None => inferred
    keep: bool = False
```

**Dependency inference.** After parsing, walk every expression in a step, collect `@name`
references, and union them into `needs`. A reference to an unknown name is a preflight error. This
is the only place dependencies come from — never trust a hand-written list alone.

---

## 7. SCLPLL v2

Whitespace-significant, line-oriented. Directives start `@` at column 0; step bodies are indented.
No backward compatibility with v1.

```
workflow   := "@workflow" IDENT [STRING] NEWLINE description?
directive  := "@var" IDENT "=" expr
            | "@input" IDENT [":" format] ["?"]        # ? = optional
            | "@output" IDENT [":" format]
            | "@mode" IDENT modeclause*
            | "@rule" IDENT "=" expr
            | "@limits" key "=" value ...
step       := "@step" IDENT ["<-" deps] ["->" outname] NEWLINE body
body       := INDENT line+ DEDENT
line       := verb args
verb       := "get"|"post"|"put"|"patch"|"delete"|"head"|"options"
            | "header"|"query"|"body"|"auth"|"paginate"|"timeout"
            | "fn"|"use"|"let"|"filter"|"join"|"sort"|"dedupe"|"save_csv"|…
            | "when"|"foreach"|"while"|"assert"|"retry"|"lane"|"tag"
```

Any registered function or plugin connector is usable as a verb — the parser resolves unknown verbs
against the function and connector registries rather than hard-coding a keyword list. That is what
keeps the grammar small while plugins stay first-class.

`emit.py` produces canonical SCLPLL from the IR: stable ordering, two-space indent, one blank line
between steps.

---

## 8. Modes and ports

**Resolution algorithm** (`run/modes.py`):

1. Resolve `extends` chain, deepest first; later specs override earlier scalars.
2. Start from all steps if `all`, else from `include` matches (id, glob, or `tag:`), else all.
3. Subtract `exclude` matches.
4. **Closure check.** For every kept step, every dependency must be kept, bound to an input port,
   available in cache under `--from-cache`, or supplied by `stub`. Otherwise: preflight error naming
   the missing producer and listing those three remedies.
5. Apply `vars` and `limit` overrides into the run config.
6. Prune the DAG. Liveness (§12) then runs against the *pruned* graph, so a partial run frees more.

Modes may not add steps, change `needs`, or alter expressions. Enforced by validating the pruned IR
is a subgraph of the full IR.

**Port binding** (`run/ports.py`), in precedence order:

1. `--in name=path` / `--out name=path` (explicit, wins)
2. Positional arguments, in declaration order: inputs first, then outputs
3. Defaults declared on the port

`-` means stdin/stdout. A glob binds the port to a sorted list of paths. Format comes from the
extension, overridable as `path:format`. Count mismatch is a preflight error listing the ports.

---

## 9. Expression language

One parser, one dispatch table. Infix is sugar: `a.total > 500` parses to `gt(a.total, 500)`.

**Paths** — `@step.body.data[0].email`, `[*]` projection, `[?(pred)]` filtered projection,
`["odd key"]` brackets. A missing path is an **error** carrying the path, the value actually present,
and the nearest valid key (Levenshtein over the sibling keys). It must never return the literal
`{{...}}`, which is the current engine's behaviour and the source of requests to malformed URLs.

**Interpolation** — `{{expr}}` inside a string stringifies at the boundary only. `@ref` outside a
string passes the typed object through.

**Dispatch** — `dispatch.py` holds `dict[(name, type), Callable]`, resolved on the runtime type of
argument one with MRO walk-up. Registration:

```python
@overload("filter", Table)
async def _(t: Table, where: Expr, *, engine: TableBackend) -> Table: ...

@overload("filter", list)
async def _(xs: list, where: Expr) -> list: ...
```

Families to implement, all resolving through the same table: comparison, logical, arithmetic,
aggregate, string, collection, relational, shape, temporal, cast. Full list in `plan.html` §07 and
generated into `docs/reference/expressions.md`.

**Safety** — a hand-written recursive-descent parser producing our own AST node types. No Python
`eval`, `exec`, or `ast.literal_eval` on user input.

---

## 10. Functions

```python
@function(name="top_customers", version=2)
async def top_customers(orders: Table, *, n: int = 10, by: str = "total") -> Table:
    """One-line summary becomes the help text."""
```

Type hints are load-bearing: they generate the JSON Schema (pydantic `TypeAdapter`), the `--help`
text, shell completion values, and the coercion that lets `"10"` from a JSON file arrive as `int`.
`version` participates in the cache key.

Both `def` and `async def` are supported; sync functions are dispatched to the thread lane
automatically unless annotated otherwise.

**Built-ins to ship (M5).** Write: `save_csv save_json save_ndjson save_parquet save_excel
save_sqlite`. Read: `read_csv read_json read_ndjson read_parquet read_excel read_sqlite glob_read`.
Convert: `convert`. Shape: `flatten explode normalize to_table infer_schema cast_schema`. Combine:
`join merge concat dedupe sort_by group_agg pivot`. HTTP: `paginate_all retry_with follow_links
parse_link_header`. Diagnostics: `assert_schema assert_rowcount profile describe sample`.

**`save_csv` flattening is the reference behaviour.** Nested objects flatten to underscore-joined
column names, deterministic column order (depth-first over first-seen keys), arrays JSON-encoded
unless named in `explode`, collisions suffixed `_2`, `columns="union"` across heterogeneous records.

---

## 11. Plugins

Discovery: `importlib.metadata.entry_points(group="sclpl.plugins")`, plus `./plugins/` and
`~/.sclpl/plugins/` for local development.

```toml
[plugin]
name = "postgres"
version = "1.2.0"
api = "sclpl/1"                         # refused if incompatible
capabilities = ["network", "secrets:read"]

[[connector]]
name = "postgres.query"
schema = "schemas/query.json"
lane = "thread"
```

A plugin may contribute: connectors, functions, DSL verbs, auth providers, paginators, table
backends. Capabilities are `network`, `fs:read`, `fs:write`, `secrets:read`, `subprocess`; they are
displayed by `sclpl plugin list` and enforceable with `--deny-capability`.

**Bundled set:** `sqlite` (query, write, exec, schema — ~150 lines, no new dependency),
`fs` (read, write, glob, watch — ~120 lines), `example` (the scaffold template). Bundled plugins use
only the public API, which is how we know the API is sufficient.

---

## 12. Scheduling, workers, memory

**Ready-queue scheduler** (`run/schedule.py`):

```
indeg = {node: len(node.needs)}
ready = heap of nodes with indeg 0, keyed by -critical_path_length
workers = N tasks, each:
    node = await ready.pop()
    async with acquire_ordered(global_sem, host_sem[node.host], tag_sems[node.tags]):
        result = await dispatch(node)          # to its lane
    store.put(node.id, result, readers=len(node.dependents))
    for dep in node.dependents:
        for input_name in dep.reads: store.release(input_name)
        if --indeg[dep] == 0: ready.push(dep)
```

Semaphores are acquired in a fixed global order (global → host → tag, each sorted by name) so the
arrangement cannot deadlock. `foreach` injects its expansion into the *same* graph — never a nested
`gather` — so fan-out obeys the global ceiling.

**Adaptive concurrency:** AIMD per host. Additive increase while p95 is flat; multiplicative
decrease on 429/503, honouring `Retry-After` exactly. Never exceeds the static caps. `--no-adaptive`
pins it. Every admission decision is logged at `-vvv`.

**Lanes.** Assigned by, in order: explicit `lane` on step or plugin manifest; the callable's
signature (`async def` → async; sync touching a `Table` → process candidate); rolling-median
statistics from run history. A size threshold prevents the process lane for small payloads.

**Handoff.** Small object → pickle. Table → Arrow IPC over shared memory, zero-copy. Already
spilled → pass the path. Large non-tabular → spill, then pass the path. Same lane → reference.

**Liveness.** After mode pruning, compute the last consumer of every binding; attach release points.
Loop bodies pin their referenced values until the loop exits (conservative by construction).
`--keep-all` disables disposal; debug mode tombstones freed bindings so a stale access raises a
named error rather than `KeyError`. `sclpl explain --memory` prints the release points.

**Governor.** Samples RSS, available memory, and fd count. Soft watermark 70% of budget: stop
admitting, prefer spilling. Hard 85%: reduce concurrency and warn with real numbers. Budget defaults
to a share of system memory; `--memory-budget 4G`.

**Cache key:**

```
blake2b(step_kind, method, resolved_url, sorted_query, body_digest,
        headers_minus_volatile, function_name, function_version,
        input_value_digests, plugin_version, engine_version,
        credential_identity_salt)     # hash of the credential, never the credential
```

Mode is deliberately **excluded**, so partial and full runs share common steps. Flags: default
(read+write), `--refresh` (write only), `--no-cache` (neither), `--offline` (read only; miss is exit
5), `--http-cache` (ETag/Last-Modified revalidation; 304 counts as a hit). Storage: content-addressed
blobs plus a SQLite index with TTL, size cap, LRU eviction.

---

## 13. HTTP transport

One `httpx.AsyncClient` per host profile for the process lifetime — HTTP/2 on, keep-alive,
`limits=Limits(max_connections, max_keepalive_connections, keepalive_expiry)`. Never a client per
request. Profiles are keyed by (scheme, host, port, auth mode, proxy, verify).

Retries: `retry.max` attempts, exponential backoff with full jitter, `Retry-After` respected
exactly, retry only on `retry_if` (default: connect errors, timeouts, 429, 5xx). A per-host circuit
breaker opens after consecutive failures and half-opens on a timer.

Paginators: `cursor`, `page`, `offset`, `link_header` (RFC 5988), `token`, plus plugin-provided.
All accept `into`, `max_pages`, `stop_when`, `concurrent`. Pages stream into the scheduler as they
arrive so downstream steps start on page one.

---

## 14. Rendering

**Event protocol** (`render/events.py`) — the engine emits these and never writes to a terminal:

```python
RunStarted(workflow, version, mode, steps_total, steps_pruned, hosts)
StepStarted(id, kind, lane)
StepProgress(id, detail, current, total)      # pages, rows, bytes
StepFinished(id, status, duration_ms, summary, cached)
StepRetrying(id, attempt, max, reason, delay_s)
ValueFreed(name, bytes)
ResourceWarning(kind, current, budget)
LogRecord(level, message, step)
RunFinished(status, duration_ms, counts, exit_code)
```

Sinks: `human` (full/simple), `plain`, `jsonl`, `quiet`. Same stream feeds all; only the sink differs.

**Terminal layer** (`render/term.py`), hand-written — see decision 7:

- **Single writer.** One task owns the stderr handle; everything else enqueues.
- **Probe once at startup:** `isatty`, `TERM`, `COLORTERM`, `NO_COLOR`, `CI`; on Windows call
  `ENABLE_VIRTUAL_TERMINAL_PROCESSING` and drop to plain if it fails. Never re-probe.
- **Ladder, descend-only:** `full` (DECSTBM `ESC[1;{rows-k}r` scroll region, colour, Unicode) →
  `simple` (repaint last k lines with `\r` + `ESC[2K`) → `plain` (one line per event).
- **Never wrap.** Measure and truncate every line to width; `os.get_terminal_size` with 80×24
  fallback; re-measure on `SIGWINCH`.
- **Probe glyphs** against the stream encoding; ASCII set on failure.
- **Restore three ways:** `finally`, `atexit`, and `SIGINT`/`SIGTERM` handlers emit `ESC[r`, show
  cursor, newline. Idempotent.
- **Bounded repaint** at ≤10 Hz with event coalescing.
- **Quarantine subprocesses:** children inherit `SCLPL_RENDER=plain`; their output is captured and
  re-emitted through the queue.
- **Escape hatches:** `--plain`, `SCLPL_RENDER=plain|simple|full`.

Verbosity: `-qq` silent, `-q` errors+summary, default step lines + live region, `-v` timings/cache/
retries/lanes/freed, `-vv` resolved vars and headers (redacted), `-vvv` bodies truncated plus
scheduler admissions. `--json` emits NDJSON on stderr and suppresses the human view.

---

## 15. CLI contract

### Bare invocation

`sclpl` with no arguments and both stdin and stderr on a TTY opens the launcher: a numbered menu —
run a saved workflow, run a file by path, validate, history, import, rerun last, environments &
secrets, settings, help, exit. Otherwise it prints help and exits `2`.

Rules: it prints the exact command before running it and asks for confirmation; plain line-based
prompts only (no cursor addressing, so it sits below the render ladder); numbers plus `q` and `?` at
every level; `Ctrl-C` backs out one level, twice exits; defaults in brackets with `Enter` to accept,
prefilled from the last run; nothing destructive without naming the target. Budget ~250 lines; it
holds no state and duplicates no logic.

### Commands

```
sclpl <workflow> [mode] [inputs…] [outputs…]      shorthand
sclpl run <workflow> --mode M --in n=p --out n=p --env E --var k=v --set path=val
    --concurrency --host-concurrency --processes --threads --connections --keepalive
    --timeout --retries --memory-budget --adaptive/--no-adaptive
    --no-cache|--refresh|--offline|--http-cache
    --from --only --skip --dry-run --keep-going --no-validate
    --name "…" --tag t --format csv|json|ndjson|parquet|xlsx|table
    -q|-v|-vv|-vvv|--json|--no-color|--plain|--log-file|--log-level|--log-format
sclpl import workflow|function|plugin|settings <src> [--as] [--project] [--recursive]
sclpl list [workflows|functions|plugins]
sclpl show <workflow>            sclpl remove <workflow> [--version N]
sclpl validate <wf> [--mode M]   sclpl explain <wf> [--mode M] [--memory]
sclpl fmt <wf>                   sclpl convert a.json b.sclpll
sclpl call GET <url> [-H] [-q]
sclpl env list|use|set|unset|show
sclpl secret set|rm|list|rotate
sclpl fn list|describe|run       sclpl plugin list|install|describe|scaffold|enable|disable
sclpl data convert|flatten|head|schema|profile
sclpl cache stats|prune|clear
sclpl runs list|show|search|diff|replay|export|pin|prune
sclpl doctor                     sclpl completion bash|zsh|fish|powershell
sclpl docs build
```

### Preflight

Runs by default on every `run`; `--no-validate` opts out. No network, no writes. Checks: parse and
schema; reference resolution; graph closure under the mode; port binding and input readability;
missing extras (prints the exact `pip install`); plugin presence, ABI, and capabilities; output
writability and overwrite confirmation.

### Exit codes

`0` success · `1` step failure · `2` usage · `3` validation · `4` assertion · `5` cache miss under
`--offline` · `6` unknown workflow or mode · `130` interrupted.

### Config precedence

CLI flag → `SCLPL_*` env → mode block → workflow file → project `sclpl.toml` → user config →
built-in default. `sclpl config show` prints the resolved value and its source for every key.

---

## 16. State and history

```sql
CREATE TABLE runs (
  id TEXT PRIMARY KEY,            -- short hash
  name TEXT NOT NULL,             -- --name, else orders-partial-0821-1432
  workflow TEXT NOT NULL, workflow_version INTEGER NOT NULL, mode TEXT,
  started_at TEXT NOT NULL, finished_at TEXT, duration_ms INTEGER,
  status TEXT NOT NULL, exit_code INTEGER,
  steps_run INTEGER, steps_skipped INTEGER, retries INTEGER,
  cache_hits INTEGER, cache_misses INTEGER, peak_rss_bytes INTEGER,
  bytes_in INTEGER, bytes_out INTEGER,
  env TEXT, pinned INTEGER DEFAULT 0, log_path TEXT
);
CREATE TABLE run_tags     (run_id TEXT, tag TEXT);
CREATE TABLE run_ports    (run_id TEXT, direction TEXT, name TEXT, path TEXT, digest TEXT);
CREATE TABLE run_steps    (run_id TEXT, step_id TEXT, status TEXT, lane TEXT,
                           duration_ms INTEGER, attempts INTEGER, error TEXT, cached INTEGER);
CREATE VIRTUAL TABLE runs_fts USING fts5(...);   -- when FTS5 is available; LIKE fallback otherwise
```

Retention `history.keep`, **default 5**, applied after each run. Pinned runs are exempt and not
counted. Each run also writes a self-contained NDJSON event log so history is greppable without the
database. `run_steps.lane` and `duration_ms` feed lane auto-tuning (§12).

**Secrets:** OS keyring first (`keyring`, optional extra); encrypted-file fallback using
`cryptography` Fernet with the key at `0600`. **If neither is available, fail — never fall back to
base64.** Redaction happens in the reporter, keyed on the set of resolved secret values.

---

## 17. Milestones

Do these in order. Each is independently demonstrable.

### M0 — Strip and skeleton — **done, 21 Aug 2026**
- [x] Deleted the whole of `app/` (not separable — `services/` imported `app.web.errors`), plus `web/`, `tools/`, `scripts/`, and the v1 tests: 250 files, 59,093 lines
- [x] Moved `docs/plan/`, the v1 docs, examples, workflows, functions, and plugins to `docs/attic/`; carry-overs preserved at `docs/attic/carried/`; deleted `start-web.*`, `sclplapi.bat/.sh`, `openapi_snapshot.json`, stray logs
- [x] Created `sclpl/` per §4; `pyproject.toml` with `[data]`, `[keyring]`, `[dev]`; entry point `sclpl = sclpl.cli.app:app`; `rich` and `textual` gone
- [x] Reporter facade + all four sinks + event dataclasses + redaction (engine emits, never prints)
- [x] CI: ruff, ruff format, mypy strict, pytest, line-budget check — on 3.11 and 3.13
- **Exit met:** `sclpl call GET https://httpbin.org/json` works and honours `-q`, `-v`, `--json`

### M1 — Typed values and expressions
- [ ] `ValueStore`, `Binding`, digests; `ValueRef` stub (spill lands in M7)
- [ ] Path resolver: dot, bracket, `[*]`, `[?(pred)]`, error with nearest-key suggestion
- [ ] Expression lexer/parser/AST; infix → canonical call lowering
- [ ] Dispatch table + comparison, logical, arithmetic, string, collection overloads for scalar/list
- **Exit:** `@a.body.items[?(price > 10)].id` evaluates; a bad path fails with a suggestion

### M2 — Scheduler and transport
- [ ] DAG build, dependency inference from refs, cycle detection, critical-path lengths
- [ ] Ready-queue scheduler, ordered semaphore acquisition, worker pool, `TaskGroup` cancellation
- [ ] Pooled `AsyncClient` per host profile, HTTP/2, retries with jitter, `Retry-After`, circuit breaker
- **Exit:** the 7-node graph in `plan.html` §10 finishes in critical-path time; 500 steps share one pool; `Ctrl-C` is clean

### M3 — The view
- [ ] `term.py`: probe, ladder, DECSTBM region, truncation, glyph probe, triple restore, ≤10 Hz repaint
- [ ] `human.py` step rows, aggregate bar, instrument line; `plain.py`; `jsonl.py`; redaction
- [ ] pty harness + golden byte snapshots at all three rungs; resize/interrupt fuzz test
- **Exit:** the §13 mockup is real; piping, resizing, and `Ctrl-C` each leave a fully restored terminal

### M4 — IR, catalogue, modes, launcher
- [ ] pydantic IR; JSON compiler; SCLPLL v2 lexer/parser/emitter; property round-trip tests
- [x] Catalogue: `import`, versioning by content hash, `list`, `show`, `remove`, name resolution order
- [x] Modes: extends, selectors, pruning, closure check with the three remedies
- [x] Ports: declaration, positional and named binding, globs, `-`, format inference, and `@step … -> port` so a writer takes its path from the binding
- [x] Preflight; `validate`, `explain`, `fmt`, `convert`; the bare launcher
- **Exit:** met — `examples/orders.sclpll` in `partial` runs 12 of its 21 steps against a live server; pruning a needed producer fails at validate time with a named fix

### M5 — Functions and tables
- [x] `Table` wrapper + `TableBackend` protocol + pandas backend; `[data]` extra with preflight message
- [x] `io.py` format dispatch; `flatten.py` with the reference semantics in §10
- [x] Built-in catalogue (37 functions); `@function` decorator, registry, schema generation
- **Exit:** met — nested JSON → flattened CSV → Excel in one pipeline, with a schema assertion

### M6 — Control flow and pagination
- [x] Five paginators streaming into the scheduler; `into`, `max_pages`, `stop_when`; `concurrent` is honoured where it is possible and reported as ignored where it is not
- [x] `foreach`, `if`, `while`, `do_while`, `gate`, `parallel` as runtime-injected subgraphs; `foreach` takes `concurrency` and `collect`
- [x] Rules blocks: `assert`, `skip_if`, `retry_if`
- **Exit:** met — a paginated source fans out into a bounded `foreach`; the bound is measured (12 items at `concurrency 3` peak at 3, against 9 unbounded)

### M7 — Memory, lanes, cache
- [ ] Liveness analysis over the pruned DAG; refcount release; tombstones; `--keep-all`; `explain --memory`
- [ ] Spill to Parquet/pickle; `ValueRef` rehydration; scratch lifecycle
- [ ] Governor with soft/hard watermarks; adaptive concurrency reduction
- [ ] Lane assignment + Arrow IPC / path handoff; content-addressed cache and all five flags
- **Exit:** intermediates at 3× budget complete by spilling; a CPU-bound join auto-lands in a process

### M8 — Plugins and the bundled set
- [ ] Entry-point discovery, manifest parsing, ABI check, capability declaration and enforcement
- [ ] Schema-driven help and completion; `plugin scaffold`
- [ ] Bundled `sqlite`, `fs`, `example` — public API only
- **Exit:** SQLite → join with an API → write back, no config; an external plugin `pip install`s and works

### M9 — Secrets, history, packaging, docs
- [ ] Keyring-first secrets, no base64 fallback; environments
- [ ] History schema, retention default 5, tags, `runs search|diff|replay|export|pin|prune`
- [ ] `doctor`, completions, wheel, `docs build` + CI drift check, four playbooks, `concepts.md`
- **Exit:** a new user imports a shared workflow and finishes a paginated API → CSV run from the README in ten minutes

---

## 18. Testing requirements

| Layer | Requirement |
|---|---|
| Unit | Every operator overload; path resolver including every failure message |
| Property | IR ⇄ JSON ⇄ SCLPLL round-trip byte-identical after `fmt` |
| Scheduler | Deterministic fake clock; assert critical-path completion; no deadlock under randomised graphs |
| pty / golden | Byte-exact snapshots at all three render rungs; resize + interrupt fuzz asserting restoration |
| Integration | Local mock HTTP server; all five paginators; retries; cancellation; partial output on `Ctrl-C` |
| Examples | Every snippet in the playbooks lives in `examples/` and runs in CI |
| Budget | Line count per package asserted against §5 of `HANDOFF.md` |
| Docs | `docs build` regenerated and diffed; non-empty diff fails |

No network in CI except the local mock server. Secrets never appear in a fixture, snapshot, or log.

---

## 19. Size budget

Revised by **ADR 0001** (23 Aug 2026): the original ~7,150 was estimated before any code
existed and omitted `expr/ops/` and `plugins_bundled/` entirely. Revised again by
**ADR 0002** (31 Aug 2026), which split `run/sclpll/` -- a lexer, parser, and emitter
that grows with the *grammar* -- out of `run/`, which grows with what the runner *does*.
Current target **~16,000 lines**, against ~59,100 deleted. Enforced in CI by
`scripts/check_budget.py`, which counts code and excludes docstrings.

| Package | Budget | | Package | Budget |
|---|---:|---|---|---:|
| `cli/` | 1,400 | | `expr/` | 1,500 |
| `render/` | 1,300 | | `expr/ops/` | 1,400 |
| `catalog/` | 500 | | `tables/` | 900 |
| `run/` | 3,600 | | `ext/` | 700 |
| `run/sclpll/` | 1,200 | | `state/` | 900 |
| `values/` | 1,000 | | `plugins_bundled/` | 600 |
| built-in functions | 1,200 | | | |

A `parent/child` key is counted on its own and excluded from its parent, so `expr/ops/`
and `run/sclpll/` cannot absorb growth belonging to `expr/` or `run/`, nor the reverse.

Dependencies, each doing three or four jobs: `httpx`, `typer`, `pydantic`, `aiosqlite`,
`pyarrow`. Extras: `[data]` (pandas, openpyxl), `[keyring]`, `[dev]`. **`rich` is not a
dependency.**

Rules: no abstraction until the second caller; reuse before writing; one mechanism per concept;
deleting counts as progress and is stated in the commit message.
