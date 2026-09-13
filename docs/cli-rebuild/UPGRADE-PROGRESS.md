# Unified upgrade progress

This checklist records implementation evidence for
[the unified upgrade plan](UNIFIED-UPGRADE-PLAN.md). A checked item has code and focused
verification behind it; unchecked work remains release scope.

See [the decision log](DECISION-LOG.md) for implementation tradeoffs and evidence.

## Batch A

- [x] A2 format/version ownership: ADR 0003 defines project schema handling and the
  policy for every later persistent format.
- [x] A4 architectural gates: budget checking refuses unbudgeted packages and layering
  checking detects directed cycles of any length.
- [x] A1 compatibility baseline: command surface, exit codes, `runs export` shape,
  plugin ABI fields, and the `call --json` event sequence are pinned in
  [BASELINE.md](BASELINE.md) and enforced by `tests/integration/test_compat_baseline.py`.
- [x] A3 metadata-first plugin activation: static discovery and CLI help avoid plugin
  import; approved inventory activation follows capability-policy validation.
- [x] A5 credential-sink audit: `secret()` now registers its resolved value with the
  run's active reporter, closing a gap where nothing ever called `Reporter.secret()`
  despite the module docstring promising it; `call --header` registers credential-shaped
  header values the same way; a failed step's persisted error is scrubbed through the
  same reporter. Command-line argv redaction was already closed separately (`safe_args`).

## Batch B

- [x] B1 strict manifest discovery and environment precedence.
- [x] B2 project initialization, `project check`, and `workflow list`.
- [x] B3 local environment selection and safe context reporting.
- [x] B4-B6 authentication providers: `auth <name>` resolves through one provider
  interface (`sclpl/project/auth.py`) to bearer/basic/api-key/custom-header profiles;
  OAuth2 client credentials (`oauth.py`) share a process-wide token cache with
  per-key locking and a bounded single refresh-and-retry on a 401; HMAC-SHA256
  request signing (`signing.py`) uses one documented canonical form. Every resolved
  credential registers with the run's reporter for redaction (reusing A5's
  `active_reporter`); a step that both names `auth` and hand-sets the same header is
  refused; cross-origin redirects verified to drop the header (httpx's own behavior).
  Known gap for D3: the step cache key partitions by auth profile *name*, not kind.

## Later batches

- [x] C1 canonical workflow identity from source and effective non-secret settings.
- [x] C2 explicit `workflow lock` generation, side-effect-free `--check` verification,
  and `run --locked` admission.
- [x] C3 versioned SQLite migration with pre-migration backups and newer-schema refusal.
- [x] C4 run provenance: a running record is persisted before scheduling; audited runs
  can require that storage admission through `--require-provenance`.
- [x] C5 process coordination: `state/locking.output_locks` extends the same
  OS-backed primitive from workflow-lock mutation to managed output destinations,
  canonicalized (resolved, case-folded on Windows) and acquired in one fixed sorted
  order so competing writers to the *same* output wait or fail with an owner while
  writers to *different* outputs never block each other. Held for a run's whole
  duration, from before the first step through scheduler completion. Verified across
  real separate OS processes. Remaining project-mutation call sites (package
  install, publication, environment selection, artifact pruning) adopt the same
  primitive as those slices land (H, E8).
- [x] D5-D6 foundation: versioned, redacted request/response fixtures support offline
  replay, recording, occurrence tracking, digest verification, and opt-in unused-fixture refusal.
- [x] D1 transport service injection: `run/retry.Clock` (injectable `now`/`sleep`/
  jitter) threads through `Pool`, `Breaker`, and `Retry.delay_for`; real time and
  randomness by default, fully deterministic "virtual time" for tests. Budget for
  the rest of Batch D recorded in ADR 0006 (`run/` 3,600 to 4,800 lines).
- [x] D2 host/proxy policy completion: unsafe HTTP methods (POST/PATCH) no longer
  auto-retry a connection error or timeout unless `retry ... idempotent=true` opts
  in explicitly (status-based retries, e.g. a 503 the server actually sent, are
  unaffected -- the exchange already completed); `HttpConfig` gained `proxy`/`verify`
  fields wired through to `Profile`/`Pool.client`, so a step-declared proxy or TLS
  setting actually reaches the request and is partitioned per auth/proxy/verify
  combination (no cross-profile leakage); a same-version wiring bug fixed along the
  way (`step.retry.on`/`max_delay` were parsed but never reached the transport).
  Retry-After date/delta and capped backoff were already correct from before D1.
- [x] D3 conditional HTTP caching: a past-TTL entry with a stored ETag/Last-Modified
  is revalidated with a conditional request under `--http-cache` rather than served
  blind or refetched outright; a 304 reconstructs the prior response and refreshes
  its validators (and counts as a cache hit), a 200 replaces it. Scoped to a single
  non-paginated, non-`extract`ing request, since a paginated step's cached value is
  already a cross-page merge and an `extract`ing step's cached value is not the
  response shape a 304 needs to rebuild -- both keep refetching outright as before.
  Credential/environment partitioning was already in the cache key (`_salt`); this
  batch only adds the request-level conditional exchange on top of it.
- [x] D4 multipart and streaming: `stream <path>` writes a response body directly to
  disk in bounded ~64KB chunks (`Pool.stream_to_file`) with an incremental SHA256, an
  atomic rename on success, and cleanup of the scratch file on any failure --
  including cancellation, which is a `BaseException` a plain `except Exception` does
  not see, so cleanup lives in a `finally`. Mutually exclusive with `paginate`/
  `extract` (rejected at IR validation) and never cached (a hit would report a file
  this run never wrote, and disk state is not assumed to persist like a response
  body). Non-rewindable streamed *uploads* are out of scope for this slice --
  request bodies remain fully-buffered typed values, which are safely retryable, so
  no new non-rewindable-retry hazard was introduced.
- [x] D7 extraction completeness signals: a paginated step's result gains a
  `completeness` field (`status: complete|partial|unknown`, `reason`, `pages`,
  `items_received`) -- `"complete"` for natural exhaustion or a bound the workflow
  or the caller actually declared (`max_pages`, `stop_when`, `--max-pages`);
  `"partial"` only when the internal hard safety net (nobody's declared bound) cut
  it short; `"unknown"` for a repeated-page anomaly, since that is neither side's
  decision. No claim about the source's real total is ever made -- only what this
  extraction covers within its own declared scope. Found and fixed a real
  pre-existing bug while testing this: the HTTP step cache key never included the
  pagination spec, so `max_pages=1` and `max_pages=40` against the same URL could
  incorrectly share a cached entry.
- Every Batch D checklist item is now checked (D1-D4, D5-D6 foundation, D7); D5-D6
  remain foundation-scoped as noted above, not a claim of the full original D5-D6
  task list.
- [x] E3 foundation: schema-versioned, project-contained test manifests execute through
  the regular runner with fixture replay offline, isolated scratch state, expected-exit,
  local contract assertions, and JSON expected-output checks.
- [x] E5 foundation: `graph WORKFLOW --format mermaid` renders a deterministic validated DAG.
- [x] E4 snapshots and changed test selection: `sclpl test run --update-snapshots`
  rewrites `expected_outputs` files in place instead of failing, comparing parsed
  JSON values rather than raw bytes -- a hand-written or differently-formatted
  snapshot that already means the same thing is left untouched, so a run never
  touches a file nothing actually asked to change -- and writes atomically (scratch
  file + `os.replace`) so a crash mid-write can never leave a half-written snapshot
  the next run would trust. `sclpl test run --changed --base REF` selects only the
  manifests a `git diff --find-renames` (plus untracked files, since a diff against
  HEAD alone misses those) against `REF` could actually affect: a manifest's own
  file, its fixture directory, or its workflow file. A change to the project
  manifest itself or to a shared `functions/`/`plugins/` directory conservatively
  selects every manifest, since those are cross-cutting. No git repository, or a
  base ref git cannot resolve, also conservatively selects everything rather than
  guessing. `sclpl test run` with no path now discovers and runs every manifest
  (previously a single manifest was required). Verified with a real git repository
  per test (subprocess, not mocked) covering renames-tracked changes, untracked
  fixture files, shared-dependency changes, project-manifest changes, and unrelated
  changes selecting nothing.
- [x] E6 audit and enforced policy: a project's `[policy]` table (`hosts`,
  `output_roots`, `overwrite`, `deny_capabilities`) is opt-in -- absent entirely, a
  project behaves exactly as before -- and enforced at the point a side effect would
  otherwise happen, never earlier and never by trusting a static check alone. Host
  allowlisting is an httpx `request` event hook registered on every pooled client,
  which httpx calls before sending the first request *and* before every redirect
  hop, so an allowlisted step can't be routed to an unlisted host by a redirect it
  never wrote. Output roots are checked against `Path.resolve()`, which follows both
  `..` traversal and symlinks/junctions to where the bytes actually land, not the
  literal path string. Overwrite is denied by default the moment a project declares
  any `[policy]` table at all (an explicit `overwrite = true`, or the per-run
  `--overwrite` flag, opts back in), checked once in `run_workflow` right after
  preflight succeeds -- before the output lock, the pool, or a single step, so there
  is nothing yet to undo. A policy denial is deliberately not a transport failure:
  it bypasses the circuit breaker and retry budget entirely rather than being
  retried or exhausting them. Project-declared `deny_capabilities` now also feeds
  the pre-existing plugin-capability-denial mechanism (which already refused a
  capability before importing the plugin module), merged with `--deny-capability`
  at CLI startup. `sclpl project check` surfaces the fully resolved policy and fails
  clearly on a malformed `[policy]` table rather than silently ignoring it.
- [x] E7 publication eligibility: `run/eligibility.py` derives, for every declared
  output with a writer step, its full dependency closure in the kept plan and the
  subset of that closure which declares its own `assert` (`derive()`) -- analysis
  only, exposed on `preflight.Report.eligibility` for `E8` to consume. Preflight
  also now hard-fails ("missing validation dependencies fail preflight") when a
  mode stubs an assert-bearing step that a declared output's writer still
  transitively depends on (`check_stubbed_validation()`): mode resolution's own
  closure check already accepts a stub as satisfying the *data*, correctly, but a
  stub never runs the `assert` it stands in for, so an output could otherwise ship
  data whose declared validation silently never happened. Found and fixed a real,
  previously-untested pre-existing bug while building this: `preflight()` built
  the execution graph (`compile_plan`) without including a mode's `stub` names in
  `available`, even though the closure check just before it does -- so any real
  workflow using `stub` on a value a kept step still reads would fail preflight
  with "nothing produces it", contradicting the closure check that had just passed
  it. The other half of this batch's accept criteria -- an assertion outrun by a
  genuinely concurrent independent branch, rather than bypassed by mode selection
  -- is not something a static check can close; that needs the write itself
  deferred, which is E8's job ("no destination changes before E7 passes").
- [x] E8 stage and publish managed outputs: opt-in via a project's `[outputs]
  publish = "validated"` (`project/outputs.py`) -- absent entirely, or a standalone
  workflow, keeps the pre-existing immediate-write behavior exactly as it was.
  Under validated publication, `-> port` writers write to a same-directory scratch
  file (`run/publication.py`'s `Ledger`) instead of their real destination, and
  nothing replaces a real destination until the *whole run* finishes with zero
  failures -- deliberately not scoped to just that output's own dependency
  closure, because SPEC 3.5 names the actual failure mode directly: an assertion
  branch and an export branch can be entirely independent, with no data
  relationship a graph-based check could ever see, so only whole-run success is
  an honest default gate. On success, every staged file is replaced atomically
  (`os.replace`, always a same-filesystem rename) and a generation manifest is
  written (`~/.sclpl/publications/<workflow>.json`) only once every file in that
  generation actually moved -- a reader following it never sees a generation the
  run did not really finish. On failure, staged files are discarded and whatever
  a previous successful run left at the real destination is untouched. A later
  file's replace failing partway through is reported as "interrupted" rather than
  silently dropped, and the files that already moved stay moved (SPEC 3.5's own
  "not a single transaction across files"). Explicitly out of scope for this
  slice, and documented as such rather than silently unhandled: validated stdout
  publication (needs spooling under a size limit; stdout stays immediate even
  under `publish = "validated"`), and SQLite's own short-transaction/rollback
  requirement (the bundled sqlite plugin writes its file directly; this
  mechanism's atomic-rename does cover the *file* as a whole once that write
  finishes, but does not add a SQL-level transaction boundary inside it).
- [x] E9 verify format fidelity: a round-trip probe of every supported format
  against the plan's own named cases (leading-zero codes, large ids, decimals,
  timezone-aware timestamps, nulls, empty tables) found two real, previously
  silent bugs, both fixed. CSV/NDJSON's `read_csv` had no protection against
  `00123` being read back as the integer `123` -- pandas' default type
  inference does not know a zero-padded code is not a number; the raw text is
  now sniffed for that exact shape (`0` followed by more digits, the shape a
  real numeric column never has) before pandas ever assigns it a dtype, and
  that column is forced to `str`. Excel writes silently gained: an integer
  above 2**53 (`123456789012345678`) came back as a *different* number
  (`...696`) with no error, because Excel stores every number as a 64-bit
  float; writing one now refuses with a diagnostic naming the exact value and
  column, matching this batch's "fail with a loss diagnostic" acceptance path
  rather than a wrong answer. A timezone-aware timestamp already raised on
  writing to Excel (pandas itself refuses), but as a raw `ValueError` --
  rewrapped as an `sclpl` diagnostic with a remedy. An empty table written as
  CSV already failed to read back (no header row to infer columns from, which
  is CSV's own real limit, not a bug); the confusing pandas
  `EmptyDataError: No columns to parse from file` is now a clear diagnostic
  naming the actual constraint. JSON, NDJSON, and Parquet already carried every
  named case correctly (Parquet keeps `Decimal` and timezone-aware `Timestamp`
  values as real typed values; JSON/NDJSON keep large integers exact and
  represent a `Decimal` as its exact decimal text, which is the closest either
  format can get to a native decimal type). SQLite is out of scope here -- it
  writes through a separate bundled plugin, not through `tables/io.py`.
- Every Batch E checklist item now has at least foundation or full coverage (E3-E9
  done; E5 foundation-scoped, E9's SQLite path out of scope, both as noted above).
- **Checkpoint E reached**: E3-E9 all have real coverage (E3/E5 foundation-scoped,
  E9's SQLite fidelity path explicitly out of scope). All five business workflows'
  existing replay tests, contracts, and negative cases continue to pass throughout.

## Batch F

- [x] F1 complete event measurements: `state/db.py`'s schema already had columns
  for per-step `attempts`/`duration_ms`/`cached`/`lane` and per-run
  `bytes_in`/`bytes_out`/`retries`, but `runner._remember` never populated them
  -- every persisted run showed `attempts=1`, `duration_ms=0`, `cached=false`,
  and zero bytes/retries regardless of what actually happened. A new
  `execute.Runtime.metrics` (keyed by graph node id, not step id, so a loop's
  separate iterations are tracked separately) accumulates HTTP attempts and
  response bytes as `_http` makes each request, and a cache hit; `schedule.
  Outcome` gained `step_durations`/`step_lanes`, populated at the same point
  the live `StepFinished` event already computes them. `_remember` now builds
  each `StepRecord` from these instead of leaving the schema's defaults, and
  sums bytes/retries onto the `RunRecord`. Found and fixed a real regression
  while testing this: reading `response.request.content` for a bytes-sent
  count raised httpx's `RequestNotRead` on a GET whose body stream was never
  marked read, breaking an unrelated existing auth-redirect test -- dropped
  in favor of only counting bytes received, which is always safely readable
  by the time a non-streaming request returns.
- Every field this touches already existed in the schema; F1 is entirely about
  actually writing to it. F2-F5 remain.
- [x] F2 reports and comparisons: `render/report.py` (new) renders one recorded
  run as human text, JSON, or self-contained HTML (`sclpl runs report <run>
  --format text|json|html [--into path]`) -- inline `<style>` only, no
  `<script>`, no external stylesheet or CDN link, and every value a response
  body could have influenced (a step's error text, the run's own name) is
  HTML-escaped before it reaches the page, so a malicious response string
  cannot inject markup into a report built from it. A step's `duration_ms`
  left at the schema's own default (`0`, from a run recorded before F1 wrote
  real numbers) renders as "unknown" rather than a fabricated zero-length
  measurement; `attempts` does not attempt the same trick, since its own
  default (`1`) is also the ordinary value for a real step that succeeded on
  its first try and the two cannot be told apart from the stored value alone
  -- documented as a known limitation rather than a false claim of full
  coverage. `db.compatible()` checks two runs share a workflow and
  environment; `runs diff` now prints a note when they do not, rather than
  silently diffing two unrelated things. `runs list`/`find`'s existing
  ambiguous-prefix handling (list the candidates rather than guessing)
  already covered this batch's "selector ties" case with no changes needed.
- [x] F3 output lineage: `run_ports.digest` (already in the schema, always written
  empty before this) now holds a real SHA256 of each bound file's actual bytes
  (`state/db.file_digest`, chunked so a large output need not fit in memory),
  computed for both input and output ports once a run finishes -- for a
  validated-publication run (E8) this runs after the real destination has been
  published, so it fingerprints what actually landed there, not a scratch file.
  A new `sclpl runs which <path>` resolves every run recorded as having
  produced a path (`History.producers_of`, compared canonically -- resolved,
  case-folded on Windows, via the same primitive C5's output locking already
  established -- so a relative and an absolute spelling of the same file
  agree), most recent first; more than one match is reported as ambiguity
  rather than silently picking one, and a digest mismatch against the file's
  current bytes is reported as "modified since this run." `cli/`'s budget rose
  1,800 to 2,000 (ADR 0007) to fit the new command; F2 had already spent it
  down to 8 lines.
- [x] F4 retention consistency: `History`'s SQLite connection now runs in WAL
  journal mode, so a reader (`runs list`, `runs which`) is served from the
  last committed snapshot instead of ever hitting "database is locked" while
  another process prunes or records a run. Nothing in the current codebase
  actually shares a blob or file across two runs' rows (each run's NDJSON log
  is uniquely named, and `_forget` only ever touches the one run id it was
  given), so "pruning one run cannot break another retained run" was already
  true by construction; this batch adds direct, comprehensive proof of it
  (every table a run's data lives in, not just the `runs` row) and confirms a
  crashed run left at `status="running"` prunes like any other row rather
  than getting stuck. Explicitly out of scope, and not yet applicable: storage
  quotas (no such mechanism exists anywhere yet), checkpoint roots (G1, not
  built), and notification references (I-batch, not built) -- there is
  nothing for retention to respect there until those systems exist.
- [x] F5 partial-result reporting and automation: `runs.completeness`
  (`"complete"`/`"partial"`/`"unknown"`) and `runs.publication`
  (`"n/a"`/`"published"`/`"withheld"`/`"interrupted"`) are new persisted
  columns, added through a real incremental migration (`state/migrations.py`
  gained an `upgrades: dict[int, str]` parameter -- `ALTER TABLE`, not the
  base schema's `CREATE TABLE IF NOT EXISTS`, is the only thing that can add a
  column to a database that already has the table) rather than assuming every
  `~/.sclpl/history.db` is freshly created. Completeness is the worst of every
  paginated step's own D7 signal across the whole run (`"unknown"` beats
  `"partial"` beats `"complete"`; a cancelled run is `"unknown"` even with no
  paginated step at all) -- deliberately whole-run, not scoped to one output's
  dependency closure, since an unrelated step's own extraction being cut short
  is real missing data regardless of what else in the run happened to succeed.
  Publication reuses E8's ledger outcome directly. `run --require-complete`
  fails a run that would otherwise exit 0 with the new `EXIT_INCOMPLETE` (7)
  when completeness is not `"complete"`, and never overrides a run that
  already failed for a real reason. `render/report.py`'s text/JSON/HTML all
  surface both fields plainly rather than only alongside `status`, so a
  `status: ok` run with `completeness: partial` cannot read as fully
  successful in any of the three formats -- the literal "cannot label partial
  data as complete" accept criterion. An old, unmigrated row reports
  `"unknown"`/`"n/a"` by the column's own default, which is the honest answer
  for a run this project never actually measured either state on.
  Explicitly out of scope, and documented rather than silently missing: JUnit
  report output (no such format exists anywhere in the codebase yet -- adding
  one is a new renderer, not a wiring task like the rest of this batch), and
  carrying these states through checkpoints/notifications (G1/I-batch, not
  built yet) or into cache entries (a real, separate piece of work: partial
  cache data must never satisfy a complete-data requirement without
  revalidation, which touches `values/cache.py`'s read path, not this batch's
  history/report surface).
- **Checkpoint F reached**: a single run's terminal summary, `runs report`
  (text/JSON/HTML), and persisted history all draw from the same sanitized
  source data (`state/db.py`'s `RunRecord`/`StepRecord`, populated by the
  live run itself in `runner.py`/`execute.py`) -- there is no second,
  independently-computed path any of them could disagree with.
- [x] G1 durable checkpoints: `run/checkpoints.py` is a new, self-contained
  `Store` for a run's completed step values, kept separate from `history.db`
  (its own `checkpoints.db`, same WAL pattern as F4). A checkpoint is only
  ever "reusable" once two things are true on disk: the blob is written to a
  scratch file and atomically renamed into its final place (never left
  half-written where a crash could leave it -- cleanup on any failure,
  cancellation included, runs in a `finally` since `CancelledError` is a
  `BaseException`), and only after that succeeds does the SQLite metadata row
  naming it get committed. `read()` never trusts the row alone: it re-hashes
  the blob against the digest recorded at write time, so a file that changed
  or vanished after being checkpointed is treated as if it were never
  checkpointed at all, not silently reused. Only two value shapes are
  eligible -- a `Table` (Parquet) and anything strict `json.dumps` accepts
  with no `default=` fallback -- everything else is simply not checkpointed
  (`write()` returns `None`, not an error); the step that produced it re-runs
  on resume, which is always correct.
- **Scope note:** G1 is deliberately a standalone library with zero callers
  today -- nothing in `runner.py`/`execute.py` invokes `Store.write()` or
  `read()` yet. Wiring it into the actual run/resume flow is G2 (resume
  eligibility planning) and G3 (resume execution), kept as separate slices so
  each piece is independently testable before the next depends on it.
- [x] G2 resume eligibility planning: `run/resume.py`'s `plan_resume()` walks a
  workflow's static plan against a specific prior run and gives every step one of
  three verdicts -- `"reuse"`, `"rerun"`, or `"refuse"` -- with a plain-language
  reason, entirely without executing anything. The comparison rests on one
  propagation rule rather than a family of special cases: a step's identity is
  only trustworthy once everything it was built from is itself trustworthy. A step
  with no step-level dependency is compared directly, by recomputing the exact
  cache key `execute._cache_key` would compute today (the same function a live run
  uses, called with the run's real current `vars`/`--var` values) and checking it
  against the digest G1's own `identity_key` persists per step (new `run_steps`
  column, added the same incremental-migration way F5's `completeness`/
  `publication` columns were -- `state/migrations.py`'s `SCHEMA_VERSION` is now 3).
  A step that reads another step's output is compared the same way, but only once
  that ancestor's own verdict is `"reuse"`, at which point its checkpointed value
  is rehydrated into a throwaway `ValueStore` so the real interpolation logic
  resolves the reference, rather than this module re-deriving an approximation of
  it. An ancestor that will rerun poisons everything downstream of it by
  construction -- nothing here recomputes what a fresh rerun would produce, so
  nothing built from it can be trusted unchanged either -- which is what satisfies
  "drift and missing artifacts invalidate affected steps and descendants" without
  a bespoke case for it. A non-idempotent HTTP write (POST/PATCH without an
  explicit `retry.idempotent`) whose prior outcome cannot be trusted -- it failed,
  its identity drifted, or its checkpoint is gone -- verdicts `"refuse"` rather
  than silently rerunning a request that may already have reached the server; the
  same write that already succeeded, with a matching identity and a valid
  checkpoint, verdicts `"reuse"` instead, which is the whole point: a confirmed
  POST must never fire twice. Dynamic control flow (`foreach`/`while`/`if`/
  `parallel`/`gate`/`use`/`let`) is a single opaque node in the static plan --
  its body is not a node until the loop itself runs -- so it (and everything
  statically downstream of it) always plans as `"rerun"`; there is no static way
  to know a loop's per-iteration identity without evaluating it, and G3, which
  actually re-expands the loop, can check each iteration's own checkpoint
  directly at that point, the same way this module checks a static step's.
  `checkpoints.Store` gained `exists(run_id, step_id) -> bool`, a cheap
  existence/integrity check that never deserializes the blob -- needed because
  `read()` returning `None` is genuinely ambiguous between "nothing was
  checkpointed" and "the checkpointed value was itself JSON `null`".
  New CLI: `sclpl runs resume-plan <run> <workflow> [--mode] [--var]` prints every
  step's verdict and reason; exits nonstandard (`EXIT_USAGE`) if anything refused.
- **Scope note:** G2 only plans; nothing here writes a checkpoint, rehydrates a
  real run, or refuses to execute anything. Wiring an actual resume (rehydrating
  eligible values into a live run and executing only what this plan says must
  rerun, including per-iteration checkpoint checks inside a re-expanded dynamic
  loop) is G3. G4 (recovering publication without duplicating it) is also not
  started.
- [x] G3 resume execution: `sclpl run --resume-from RUN` actually rehydrates a
  prior run's reusable checkpoints and executes only what G2's plan says must
  rerun, under a new run linked to its parent (new `runs.parent_run_id` column).
  Two real gaps this closed, discovered only once execution -- not just
  planning -- was wired up: (1) nothing had ever called `checkpoints.Store.write()`
  from the actual run path, so G1/G2 had no data to ever find reusable in
  practice; `execute.py`'s `run_step()` now checkpoints every cacheable step's
  value (cache hit or a fresh fetch alike) under the run's own id, gated on
  `--no-record` the same way history itself is, never on the run's own
  `--no-cache`/`--refresh` flags. (2) a dynamic loop's real node id
  (`control.MARK` is `"::"`) is not a valid filename on Windows -- `:` is
  reserved for drive letters there -- so `checkpoints.py`'s blob path now
  sanitizes the step id for the filesystem while leaving the id itself (stored
  in SQLite, compared during planning) untouched; caught by a real integration
  test failure, not by inspection, and now pinned with a dedicated unit test.
  `runner._resume()` runs G2's `plan_resume` against short-lived history/
  checkpoint/cache handles (nothing here is a side effect, so a refusal at this
  point has touched nothing that needs undoing): a refused, unacknowledged step
  fails the run before any history row, lock, or connection is opened, naming
  every refused step and its reason with the remedy (`--force-resume STEP`,
  repeatable, an explicit per-step acknowledgment, never a blanket bypass);
  otherwise every reused step's checkpointed value becomes a stub (the exact
  mechanism mode-pruning already uses for a value nothing in this run
  produces) and the executed plan is `Plan.subgraph`-pruned to exclude them, so
  a reused step is never scheduled at all, not merely fast. A resumed run's own
  completeness can never read better than the parent's: a reused step's data
  was never re-extracted by this run, so if the parent's own overall
  completeness was `"partial"`/`"unknown"`, this run inherits that ceiling
  (F5's own scope note anticipated exactly this, deferring it until checkpoints
  existed to carry it through).
- **Scope note:** a reused step's `assert` is not re-checked -- the same
  pre-existing precedent as a mode stub (`eligibility.check_stubbed_validation`
  already documents this for stubs generally; G3 does not introduce a new gap,
  it inherits the one that already exists for mode-pruned values). Per-iteration
  reuse inside a dynamic loop is not planned statically (G2's own documented
  scope: a loop's body is not a node until it runs) -- G3 likewise does not
  special-case it; the whole loop reruns as a unit if anything upstream of it
  drifted, which is correct, if not maximally fine-grained. G4 (recovering
  publication state itself without duplicating it -- generation identifiers,
  completion receipts, destination-digest validation under C5 locks) is not
  started; G3's own publication path is unaffected only in the sense that a
  reused step was never scheduled, so it never appears as a failure either --
  publication proceeds exactly as if every step, reused or rerun, succeeded.
- [x] G4 recover publication without duplicating it: `run/publication.py`'s
  `publish()` now writes a durable per-generation intent record (every port's
  scratch path, real destination, and scratch-content digest) *before* the
  first file moves, and removes it once its own replace loop returns control
  -- success or partial failure alike. A crash between committing one file and
  the next (the process killed outright, not merely a step failing) leaves
  that record behind as the only evidence of what was in flight, since the
  process that started the generation never got to say what happened to it.
  New `recover(workflow)` reads it back: a port whose scratch file still
  exists never got its `os.replace`, and is completed now; a port whose
  scratch file is already gone was already committed, verified against the
  digest recorded at intent time rather than trusted on the strength of the
  file simply being present (a destination that no longer matches is reported
  `tampered`, not silently accepted); and if a *newer* generation has already
  published since the crash (the current manifest names a different
  generation), the old, interrupted one is reported `ambiguous` and nothing is
  touched -- completing it now could overwrite a newer, complete generation
  with an older, partial one. New `sclpl runs recover-publication <workflow>`
  acquires the same C5 output locks a run itself would hold over the
  destinations involved before touching anything, so recovery never races a
  concurrent run or another recovery attempt. The intent record is keyed per
  *generation*, not merely per workflow (`{workflow}.{generation}.pending.json`)
  -- an early version kept one shared record per workflow, and a real test
  caught it being silently overwritten by an unrelated, later publish attempt
  before `recover()` ever got to see the crash it was meant to preserve
  evidence of.
- **Batch G complete** (G1-G4): durable checkpoints, resume eligibility
  planning, resume execution, and publication crash-recovery are all real,
  tested, and wired end to end through the CLI (`sclpl run --resume-from`,
  `sclpl runs resume-plan`, `sclpl runs recover-publication`).

## Batch H

- [x] H1 package manifest/build: new `sclpl/packages/build.py` bundles a project's
  declared workflow/test directories, conventional `docs`/`schemas`/`fixtures`/
  `plugins` directories, `[package.include]` globs, and locally-registered Python
  scripts into one `.sclplpkg` zip archive. New `sclpl package build` CLI command
  (`cli/package_cmd.py`). Accept criteria verified: two builds of unchanged content
  are byte-identical (fixed ZIP timestamps, fixed `create_system`, sorted entries,
  fixed compresslevel -- `test_build_is_byte_identical_across_repeated_builds`);
  secrets (`.env*`, `*.pem`, `*.key`), hidden files/dirs, `__pycache__`, and
  declared `[policy] output_roots` are excluded even when an `[package.include]`
  glob would otherwise sweep them up (`test_build_excludes_*`). The archive embeds
  a `PACKAGE.json` manifest listing every entry's own SHA-256 plus one aggregate
  digest, so "did the content change" never requires re-downloading the archive to
  check. ADR 0011 budgets `sclpl/packages` at 1,600 lines.
- [x] H2 validation/install: new `sclpl/packages/install.py`. `validate()` checks a
  package archive without extracting or executing anything from it: unsupported
  schema, an undeclared or missing archive entry, a per-file digest mismatch
  against the manifest (tamper/corruption detection), path traversal (`../`,
  absolute, or drive-letter entry names), a symlink/device/FIFO/socket entry
  (refused by its Unix mode bits; a mode with no type bits set -- the common case
  for a plain `zipfile.writestr` -- is treated as an ordinary file, not refused),
  a case-insensitive filename collision, and archive-bomb ceilings (entry count,
  total uncompressed size, per-entry compression ratio). `install()` validates
  first, extracts into a fresh staging directory, and only does one atomic
  `Path.replace` into `<into>/<name>/<version>` -- a validation failure never
  creates a staging directory at all, and any failure during extraction is
  cleaned up before the exception propagates, so an existing good install (or no
  install at all) is always what remains. Reinstalling the same name/version is
  refused rather than silently overwritten. New `sclpl package validate` and
  `sclpl package install` CLI commands. Compatibility (declared `sclpl` version
  constraints) and capability-policy comparison against a prior install are H3's
  concern, deferred until there is a "prior install" to compare against.
- [x] H3 plugin lifecycle (inspect/verify/update/remove): new
  `sclpl/packages/lifecycle.py` operates on the locked inventory H2's
  `install()` built (`~/.sclpl/packages/<name>/<version>`). `list_installed`/
  `describe` inspect it; `verify` re-hashes every installed file against its
  own recorded manifest today, catching drift that happened *after*
  installation (a corrupt/tampered install-time archive is H2's `validate`'s
  job, not this). `diff` compares two installed versions' file listings
  (added/removed/changed) for an explicit update diff. `remove` is
  dependency-aware against a new `[package.requires]` project-manifest table
  (name -> pinned version): removing a version currently pinned by the loaded
  project is refused unless `--force`, so "no silent plugin upgrade during
  run" and "a referenced version cannot disappear without a clear refusal"
  both hold. New `sclpl package list/show/verify/remove/update` commands;
  `update` installs a new version *alongside* any existing ones (never
  removes or replaces silently) and prints the file diff against the
  previously installed version. ADR 0012 budgets `cli` at 2,450 lines.
- [ ] H4 shared distribution (registry client): not started.
- [ ] H5 registry release workflow: not started.
