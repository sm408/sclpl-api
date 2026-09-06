# Unified upgrade decision log

This is a running implementation record for the unified upgrade. Each entry captures
the decision, its tradeoff, and the evidence available when it was made.

## 2026-09-05 — Integration branch before final merge

- **Decision:** Work on `integration/unified-upgrade`, with small reviewable commits,
  then merge/squash only after the full release gates pass.
- **Why:** Direct commits to `main` were rejected by the automated reviewer. The branch
  preserves recoverable checkpoints while respecting the requested final one-branch
  release state.
- **Evidence:** GitHub tracks the branch after the authorized push. Current commits are
  `3a5eada`, `4fa4b80`, `b30d418`, `d7f338f`, and `2da07cc`.

## 2026-09-05 — Project context and manifest schema

- **Decision:** Use a strict `sclpl.toml` schema version 1, nearest-root discovery, and
  explicit environment precedence: CLI, `SCLPL_ENV`, local selection, project default.
- **Tradeoff:** Unknown manifest keys fail early, which prevents forward-compatible
  guessing but requires deliberate format migrations.
- **Evidence:** `project check`, `env`, `workflow list`, and focused project tests.

## 2026-09-05 — Budget and architecture gates

- **Decision:** Budget `sclpl/project/`, raise measured CLI capacity, reject unbudgeted
  top-level packages, and detect directed layering cycles of any length.
- **Tradeoff:** The total line budget increased to 18,400, documented by ADR 0003,
  instead of hiding new code outside the gate.
- **Evidence:** `check_budget.py`, `check_layering.py`, and ADR 0003 pass on the branch.

## 2026-09-05 — Workflow identity and locks

- **Decision:** Lock workflow source and effective non-secret configuration with a
  versioned `sclpl.lock`; `--check` and `run --locked` never rewrite it.
- **Tradeoff:** The first identity excludes full plugin/function dependency closure;
  later lock work must extend the same schema rather than create another lock format.
- **Evidence:** focused lock tests and `init → workflow lock → run --locked --dry-run`.

## 2026-09-05 — History migrations

- **Decision:** Version history SQLite using `PRAGMA user_version`, back up pre-existing
  unversioned databases, and refuse databases created by newer software.
- **Tradeoff:** The initial migration is deliberately narrow; later schema changes must
  add explicit ordered migration steps.
- **Evidence:** isolated SQLite migration smoke test plus Ruff, mypy, budget, and layering checks.

## 2026-09-05 — Secret-safe history and start provenance

- **Decision:** Redact sensitive CLI arguments before history persistence and create a
  `running` run record before scheduled side effects.
- **Tradeoff:** Generic value redaction is heuristic; authentication profiles and managed
  artifacts still need their dedicated sink-by-sink controls in later batches.
- **Evidence:** safe-argument unit tests and a CLI provenance smoke test.
- **Follow-up:** Dry runs must not create a `running` history row because they have no
  durable execution outcome. The correction is included in the next commit.

## 2026-09-05 — Fixture storage primitive

- **Decision:** Store versioned request metadata separately from content-addressed body
  blobs, and identify repeated identical requests with an explicit occurrence number.
- **Tradeoff:** This is a reusable storage primitive; transport interception and CLI
  recording/replay remain the next integration slices.
- **Evidence:** isolated record/replay smoke check confirms authorization headers are
  excluded from metadata and body lookup is digest-verified.

## 2026-09-05 — Offline transport injection

- **Decision:** `Pool` accepts an optional fixture store and serves matching responses
  before client creation; repeated requests consume separate occurrence fixtures.
- **Tradeoff:** CLI flags and recording still need to supply the store in a later slice.
- **Evidence:** isolated offline transport smoke test completed without a live client.

## 2026-09-05 — CLI single-request replay

- **Decision:** Add `sclpl call ... --replay PATH` as the first public consumer of the
  fixture transport.
- **Tradeoff:** It establishes offline request behavior before workflow-wide recording
  and replay options are added, keeping one transport path rather than a mock client.
- **Evidence:** CLI smoke test returned the recorded body from `offline.test` without a
  network request.

## 2026-09-05 — Workflow replay injection

- **Decision:** Add `run NAME --replay PATH`, passing fixtures through runner options
  into the existing pooled transport used by workflow steps.
- **Tradeoff:** The target grouped `workflow replay NAME --fixture PATH` alias and
  recording option remain follow-up CLI work; behavior is already exercised through
  the regular scheduler and HTTP step path.
- **Evidence:** an offline fixture-backed workflow completed successfully against
  `offline.test` with no live transport client.

## 2026-09-05 — Grouped replay command

- **Decision:** Expose `workflow replay NAME --fixture PATH` as a thin CLI adapter to
  the existing runner replay option.
- **Tradeoff:** One runner path keeps retry, scheduling, diagnostics, and fixture behavior
  consistent; command code contains no second execution implementation.
- **Evidence:** generated command help confirms the required workflow name and fixture path.

## 2026-09-05 — Fixture recording transport hook

- **Decision:** Let the shared transport record successful response metadata and bodies
  into the fixture store, including fixture-served responses.
- **Tradeoff:** CLI recording starts with `call --record`; workflow recording remains a
  thin follow-up option over this same hook.
- **Evidence:** static checks pass; the fixture-origin recording bypass was caught and
  corrected during the record/replay smoke exercise.

## 2026-09-05 — Workflow fixture recording

- **Decision:** Add `run NAME --record PATH`, passing the recorder through immutable
  runner options to the same transport pool used for workflow HTTP steps.
- **Tradeoff:** A workflow run can now record and replay with shared primitives; policy
  validation and richer fixture selection remain later Batch D work.
- **Evidence:** CLI help, Ruff, and mypy validate the public contract and wiring.

## 2026-09-05 — Shared contract evaluator

- **Decision:** Start contracts with a strict documented JSON-compatible subset and
  raise the existing `AssertionFailed` diagnostic type.
- **Tradeoff:** Remote references and broader JSON Schema dialect features remain disabled
  until they have explicit security and compatibility rules.
- **Evidence:** nested type, required-field, enum, and bounds tests exercise value paths.

## 2026-09-05 — Contract package budget

- **Decision:** Add `sclpl/contracts/` as a 700-line budgeted package and raise the total
  target to 19,100 lines; record the change in ADR 0004.
- **Tradeoff:** The increase is explicit and reviewable; contract code cannot evade the
  architecture gate by living in an unlisted directory.

## 2026-09-05 — Local contract command

- **Decision:** Expose `contract check VALUE CONTRACT` for local JSON values and local
  JSON contract files only.
- **Tradeoff:** Contract-reference network access is deliberately absent; it needs
  explicit allowlist and caching policy before becoming a supported behavior.
- **Evidence:** command help, Ruff, and mypy validate the route and typed input surface.

## 2026-09-05 — Local contract generation

- **Decision:** Generate conservative candidate contracts from local JSON samples and
  require a new `--into` destination when saving.
- **Tradeoff:** A single sample cannot prove optionality or heterogeneous shapes, so the
  output is explicitly a candidate and never overwrites an accepted baseline.
- **Evidence:** nested candidate generation tests pass alongside the contract checks.

## 2026-09-05 — Project test-manifest discovery

- **Decision:** Use schema-versioned TOML manifests discovered only below declared,
  project-contained test directories; validate them before any run is eligible.
- **Tradeoff:** This slice does not execute workflows yet. It makes fixture, expected
  exit, assertions, and output expectations explicit so the later runner can isolate
  state and remain offline by default.
- **Evidence:** discovery, field validation, and fixture-path escape tests cover the
  local manifest boundary. ADR 0005 records the new package budget.

## 2026-09-05 — Local contract references

- **Decision:** Resolve local JSON contract `$ref` values relative to the current
  contract file and reject remote references and paths escaping the contract root.
- **Tradeoff:** The supported dialect is intentionally small: JSON-pointer fragments
  and local JSON documents only. Remote fetch, caching, and trust policy remain absent.
- **Evidence:** focused tests cover a local referenced definition and remote-reference
  refusal; contract checks continue to use assertion exit semantics.

## 2026-09-05 — Conservative array contract candidates

- **Decision:** Merge all observed array elements when generating a candidate: retain
  only common required object fields and leave heterogeneous item constraints open.
- **Tradeoff:** Candidate contracts avoid false breakage from one incomplete or mixed
  sample, at the cost of requiring a reviewer to strengthen deliberately loose fields.
- **Evidence:** focused tests cover optional fields inferred from differing samples and
  unconstrained heterogeneous arrays.

## 2026-09-05 — Plugin metadata before activation

- **Decision:** Plugin discovery can return manifests without importing modules; the
  `plugin list --static` surface uses this path.
- **Tradeoff:** Entry-point metadata without a discoverable manifest remains minimally
  described until explicit activation; inspection never executes its module to fill gaps.
- **Evidence:** import sentinels remain unexecuted during static discovery and capability
  refusal, so policy is evaluated before activation.

## 2026-09-05 — CLI plugin activation boundary

- **Decision:** CLI import registers built-ins only. The root callback validates denial
  policy before activating plugins, while `plugin list --static` skips activation entirely.
- **Tradeoff:** Plugin-provided runtime contributions are unavailable during command
  routing, which keeps help and static inspection safe; activation occurs before normal
  command execution.
- **Evidence:** static inspection reports bundled plugins as unactivated and the denial
  sentinel test confirms refused modules are never imported.

## 2026-09-05 — Required run provenance

- **Decision:** Preserve best-effort history for ordinary runs, while
  `run --require-provenance` refuses to schedule when its initial provenance record
  cannot be written.
- **Tradeoff:** Audited runs trade availability for a durable pre-side-effect identity;
  ordinary interactive use retains the prior nonfatal history behavior.
- **Evidence:** a storage-fault test verifies that scheduler admission fails before the
  workflow can execute.

## 2026-09-05 — Project mutation lock

- **Decision:** Use a short OS-backed lock for workflow-lock writes, with bounded waits
  and a separate owner marker for Windows-readable contention diagnostics.
- **Tradeoff:** This first integration protects project metadata; output ownership and
  additional project mutations will use the same primitive in later slices.
- **Evidence:** focused contention testing reports the holder PID, and workflow lock
  generation/verification regression tests pass.

## 2026-09-05 — Manifest contract assertions

- **Decision:** Test manifests name a produced step and a local contract file; successful
  offline runs validate that stored value through the shared contract evaluator.
- **Tradeoff:** Assertions are deliberately local and explicit. Snapshot and structured
  output comparison remain separate test-runner work.
- **Evidence:** a project test workflow produces an integer that satisfies its declared
  local contract during isolated execution.

## 2026-09-05 — Manifest expected outputs

- **Decision:** Expected outputs map produced step names to local JSON files and compare
  values deterministically after successful test execution.
- **Tradeoff:** This establishes exact JSON value checks; logical table snapshots and
  update workflows remain separate snapshot work.
- **Evidence:** the isolated workflow test verifies both an integer contract and its
  expected JSON value.

## 2026-09-05 — Workflow Mermaid graph

- **Decision:** Expose `graph WORKFLOW` using the existing validated plan, emitting
  stable Mermaid nodes and dependency edges.
- **Evidence:** a two-step workflow smoke test emitted its two nodes and one edge.

## 2026-09-05 — Strict replay fixture consumption

- **Decision:** `run --strict-replay` rejects successful replay when any recorded
  request fixture remains unused.
- **Tradeoff:** Strictness is explicit so partial or intentionally broad fixture sets
  retain the existing replay behavior unless the caller opts in.
- **Evidence:** fixture tests track consumed metadata separately by occurrence, and the
  run command exposes the strict admission option.

## 2026-09-05 — Offline manifest test execution

- **Decision:** `test run` executes one validated project manifest through the regular
  scheduler with fixture transport, no history, no cache, and a unique test-state root.
- **Tradeoff:** Output snapshots and declarative assertion execution remain follow-up
  work; this slice establishes the isolated, offline execution boundary they require.
- **Evidence:** an end-to-end manifest test runs a project workflow and verifies its
  scratch directory is contained below `.sclpl/tests`.

## 2026-09-06 — A5 credential-sink audit closes the dead redaction path

- **Decision:** `secrets_fns.secret()` now looks up the currently active `Reporter`
  through a new `sclpl.render.reporter.active_reporter()` context var and registers its
  resolved value with it (`reporter.secret(found)`), instead of only returning the value.
  `sclpl call --header` registers header values under known credential-shaped names
  (`authorization`, `proxy-authorization`, `cookie`, `x-api-key`, `api-key`) the same way.
  A new `Reporter.scrub(text)` method exposes the reporter's redaction outside the event
  pipeline, and `runner._remember` now uses it to scrub a failed step's persisted error.
- **Why:** `secrets_fns.py`'s own module docstring has promised since it was written that
  "redaction happens in the reporter, keyed on the set of resolved secret values, so this
  can return the real thing and every sink still shows it redacted" — but nothing in the
  codebase ever called `Reporter.secret()`. Every workflow that used `secret()` (the
  documented pattern is `@var token = "{{secret('api_token')}}"` feeding a header) had its
  real credential value flow through every event the reporter processes with no redaction
  at all, because the redactor's value set was always empty. Command-line argv redaction
  had already been closed separately (`sclpl/state/safe_args.py`, commit `d7f338f`), but
  that fix does not cover values a workflow resolves at runtime rather than typing on the
  command line, and it does not cover step failure messages.
- **Tradeoff:** The context var only crosses an `async with Reporter(...)` boundary on the
  same OS thread; a function dispatched to a process lane would not see it. `secret()` is a
  small, synchronous, string-returning call, so it is never assigned a process lane in
  practice, but this is a real limitation rather than a general-purpose mechanism, and a
  future secret-resolving builtin that legitimately needs a process lane will need its own
  registration path. Header credential detection is name-based (a fixed list mirrored from
  `run/fixtures.py`'s own forbidden-header set, extended with common API-key spellings) —
  it protects known-shaped credentials, not arbitrary secret-carrying headers.
- **Evidence:** `tests/unit/test_secrets_fns.py` proves a value resolved via `secret()`
  inside an expression is unreadable through the same reporter immediately afterward, and
  that a missing/too-short secret is still handled correctly. `tests/unit/test_call_headers.py`
  covers the same for `call --header`. `tests/unit/test_runner.py` proves a step error
  containing a resolved secret is scrubbed before it reaches the history database, while an
  ordinary error is left readable. `tests/unit/test_reporter.py` covers the new `scrub()`
  method and the `active_reporter()` context var directly.

## 2026-09-06 — A1 compatibility baseline

- **Decision:** Pin the top-level command list, exit code numbers, `runs export` JSON
  top-level shape, plugin ABI field set, and the `call --json` event sequence in
  `docs/cli-rebuild/BASELINE.md`, enforced by `tests/integration/test_compat_baseline.py`.
- **Tradeoff:** Performance budgets (plan section 8) are deliberately out of scope here;
  they need a stable benchmark machine to calibrate against and belong with J3. This
  baseline fixes the *shape* of the public surface, not its throughput.
- **Evidence:** `test_compat_baseline.py` fails if a baseline command disappears, an exit
  code is renumbered, `runs export`'s top-level keys change, or a required `Plugin` field
  is removed. Batch A is now fully closed (A1-A5).

## 2026-09-06 — B4-B6 named auth profiles

- **Decision:** One provider interface (`sclpl/project/auth.py`) resolves `auth <name>`
  (already a defined but unused field on `HttpConfig`) into headers/query. Static kinds
  (bearer, basic, api_key, header) resolve without network access; OAuth2 client
  credentials (`sclpl/project/oauth.py`) and HMAC-SHA256 signing
  (`sclpl/project/signing.py`) are separate modules dispatched from the same `apply()`.
  `runner._auth_profiles` loads them from the project manifest's `[auth.<name>]` tables,
  defaulting each profile's secret namespace to the project's currently selected
  environment. `execute._apply_auth` refuses when a step both names `auth` and
  hand-sets the header that profile would write, and retries exactly once, with a
  freshly fetched token, when an oauth-backed request gets a 401.
- **Why:** The field existed in the IR and was already used to partition the step cache
  key, but nothing ever applied it to a request -- `auth bearer` on a step was silently
  a no-op. Every workflow needing real authentication had to hand-write
  `header Authorization: Bearer {{secret(...)}}` instead.
- **Tradeoff:** The step cache key still partitions by the auth profile's *name*, not
  its resolved kind/identity -- resolving that fully would mean doing the (possibly
  network-touching) resolution just to compute a cache key, defeating the point of
  caching. A workflow that changes a profile's `type` while keeping its name could see
  a stale cached response; full "cached bodies never cross auth identities" is D3's
  explicit job. Cross-origin redirect stripping relies on httpx's own behavior
  (verified, not reimplemented) rather than a custom mechanism.
- **Evidence:** `tests/unit/test_auth.py` and `test_signing.py` cover parsing,
  validation, and the static/HMAC resolution paths, including a byte-exact HMAC vector.
  `tests/integration/test_oauth.py` proves token caching, concurrent-request sharing
  (twenty concurrent callers produce one issuance), expiry-triggered refresh, and
  rejection handling against a real local token endpoint.
  `tests/integration/test_auth_e2e.py` runs a full project workflow through
  `run_workflow` for each kind against a real server, including the conflict refusal,
  the unknown-profile error, the 401-refresh-and-retry, and the cross-origin redirect
  case. Batch B is now fully closed (B1-B6).

## 2026-09-06 — C5 output ownership

- **Decision:** Extend the OS-backed `Lock` primitive already used for workflow-lock
  writes (`sclpl/state/locking.py`) to managed output destinations. A new
  `output_locks(paths)` canonicalizes each path (resolved, case-folded on Windows),
  deduplicates, sorts them into one fixed order, and acquires a lock file beside each
  destination (`<file>.sclpl-lock`) rather than in a project-wide registry, since a
  managed output need not live inside any project. `runner.run_workflow` holds these
  locks for the run's entire duration -- from before the first step runs through
  scheduler completion -- over every port-bound output, before any step can write.
- **Why:** Two runs racing the same output file could interleave writes into it with
  nothing stopping them; a workflow with several output ports needs its locks
  acquired in the same order every time, or two runs wanting the same two outputs in
  opposite order could deadlock each other.
- **Tradeoff:** Only port-bound (`-> name`) outputs are covered -- an ad-hoc
  `save_csv(..., "/explicit/path")` inside a function call is, per section 3.5, an
  explicit side effect outside managed publication, so it is not locked here. The
  lock is acquired with a blocking, synchronously-polling primitive; that is fine
  because each `sclpl run` is its own OS process with nothing else on its event loop
  at that point, but it means two `run_workflow` calls sharing one event loop
  (as in-process tests sometimes do) would stall each other rather than run
  concurrently -- real usage is unaffected.
- **Evidence:** `tests/unit/test_locking.py` proves non-conflicting outputs never
  wait on each other, the same output is exclusive, case/relative-segment aliases on
  Windows collide on one lock, opposite acquisition orders never deadlock (two real
  threads, both complete), and a *separate process* holding the lock is a visible,
  named owner. `tests/integration/test_output_locking.py` proves it through the real
  CLI: a `sclpl run` targeting an output another process holds waits for it and then
  succeeds, while one targeting a different output is never slowed down. Batch C is
  now fully closed (C1-C5). Note for D: `run`'s budget headroom is down to 96 lines
  (of 3600); the D batch will likely need a budget revision.

## 2026-09-06 — D1 transport service injection

- **Decision:** Add `run/retry.Clock` (`now`, `sleep`, `jitter`, real by default) and
  thread it through `transport.Pool` (constructor `clock=` parameter, replacing direct
  `time.perf_counter`/`asyncio.sleep` calls) and `retry.Breaker` (`now=` field,
  replacing direct `time.monotonic()`), and give `Retry.delay_for` an optional
  `jitter` parameter that a caller can supply instead of it drawing its own via
  `random.random()`.
- **Why:** D2's virtual-time breaker-transition testing and any deterministic backoff
  test need to advance time and fix randomness without a real wait or monkeypatching
  a stdlib module global (which would affect every other test in the process). Every
  default stays real time and real randomness, so this is additive infrastructure,
  not a behavior change.
- **Tradeoff:** Also budgeted `run/` up from 3,600 to 4,800 lines (ADR 0006, total
  19,800 to 21,000) ahead of D2-D4/D7, since D1 alone used the package's last 81
  lines of headroom and every remaining D task lands in `run/`.
- **Evidence:** All existing transport/retry/call/pagination/scheduling tests pass
  unchanged (the explicit D1 accept criterion). New tests: an injected `jitter` makes
  `delay_for` deterministic while an uninjected call still draws real randomness; an
  injected `Breaker.now` proves the exact reset-window boundary without a
  `reset_after=0.0` trick; a `VirtualClock`-backed `Pool` retries a real flaky local
  endpoint against a 100-second nominal backoff and the test still completes in well
  under a second, with the chosen delays recorded rather than actually waited out.

## 2026-09-06 — D2 host/proxy policy completion

- **Decision:** `retry.Retry` gains `idempotent: bool = False` and
  `allows_transport_retry(method)`; `Pool.request` consults it before retrying a
  connection error or timeout (never before retrying a status the server actually
  sent -- that exchange already completed, so `should_retry_status` is unaffected).
  `HttpConfig`/the SCLPLL parser gain `proxy`/`verify` request verbs and `ir.Retry`
  gains `idempotent`, both flowing generically through the existing
  `model_validate`/`model_dump(exclude_defaults=True)` round trip with no new parser
  cases needed for the retry field. `Pool.request` gains `auth`/`proxy`/`verify`
  keyword parameters that build the connection `Profile`, so those three are
  partitioned per-connection exactly like the host already is.
- **Why:** GET/HEAD/OPTIONS/PUT/DELETE are safe to repeat blind because HTTP defines
  them idempotent; POST/PATCH are not, and a timeout does not say whether the server
  ever saw the request, so retrying it automatically risks a double-submit. Along the
  way, found and fixed a real pre-existing gap: `step.retry.on` (extra retry statuses)
  and `step.retry.max_delay` were parsed into the IR and round-tripped by `fmt`, but
  `execute._http` never read them when building the transport `Retry`, so a workflow
  declaring `retry 3 on=[400]` silently got the default status set instead.
- **Tradeoff:** Also fixed a latent bug the new `verify` plumbing would otherwise have
  introduced: `Pool.client` used to AND `profile.verify` with the pool's own default a
  second time, which happened to be a no-op while `Profile.of` was always called with
  the pool's default value, but would have let a globally-insecure pool silently
  overrule a step that explicitly asked for verification. Fixed to use the
  already-resolved `profile.verify` as-is.
- **Evidence:** All existing transport/retry/call/pagination/workflow tests still
  pass unchanged. New tests: a POST against a real closed port (a pure transport
  failure, no response) is not retried by default and fails on the first attempt; the
  same GET is retried twice per policy; `idempotent=True` lets the POST retry too; a
  small local recording server proves a declared `proxy=` actually receives the
  absolute-URI request line HTTP defines for forward proxies; `Profile.of` produces
  distinct profiles for distinct auth/proxy/verify values against the same host.

## 2026-09-07 — D3 conditional HTTP caching

- **Decision:** `values.cache.Entry` gains `fresh: bool`; `Cache.get` returns a
  past-TTL entry (instead of a miss) only when the policy allows revalidation *and*
  the entry actually has an ETag or Last-Modified to send -- nothing to revalidate
  with is the same as no permission to. `execute.Runtime` gains two small transient,
  per-node dicts: `pending_revalidation` (a stale `Entry` for `_http` to consume) and
  `cache_validators` (the ETag/Last-Modified a response carried, for `run_step` to
  store once the step returns). `_http` adds `If-None-Match`/`If-Modified-Since` to a
  revalidation request; a 304 reconstructs the prior stored response shape and
  refreshes its validators (counting as a cache hit); a 200 replaces it outright.
- **Why:** The storage half of this (the `etag`/`modified` columns, the `revalidate`
  policy flag, the credential-salted key) already existed, but nothing ever sent a
  conditional request or read a 304 -- `--http-cache` enabling `revalidate=True` on a
  stale entry silently served the old value with no server contact at all, which is
  not what "revalidate with ETag; a 304 counts as a hit" (the module's own docstring
  table) promises.
- **Tradeoff:** Deliberately scoped to one non-paginated, non-`extract`ing request.
  A paginated step's cached value is a merge across pages with no per-page
  validators tracked; an `extract`ing step's cached value is whatever expression it
  computed, not a `{status, headers, body, url}` shape a 304 could reconstruct.
  Both keep refetching outright on expiry, exactly as before this batch -- this is a
  real limitation, not a hidden one, and matches "distinguish HTTP revalidation from
  step-result caching" rather than conflating the two.
- **Evidence:** `tests/unit/test_memory.py` proves the entry/miss/revalidatable
  three-way split, including that a validator-less stale entry is still a plain
  miss. `tests/integration/test_http_cache.py` runs the real runner against a real
  local ETag-aware server: an unchanged resource is served via a confirmed 304 (one
  real request per run, not zero); a changed resource replaces the cached value; a
  still-fresh entry never touches the network at all; `--http-cache` off keeps the
  pre-D3 behavior of an outright refetch on any stale entry.

## 2026-09-07 — D4 bounded-memory streaming downloads

- **Decision:** A new `stream <path>` request verb (`HttpConfig.stream_to`) routes
  through a new `Pool.stream_to_file`, which uses `httpx`'s streaming API to write a
  response in `STREAM_CHUNK_BYTES` (64KB) pieces to a scratch file beside the
  destination, hashing incrementally as it goes, then `os.replace`s it into place
  only once the whole body has arrived. `stream_to` is rejected at IR validation
  when combined with `paginate` or `extract`, and `_cache_key` returns `None` for it
  outright (never cached, like the existing writer-function exclusion).
- **Why:** Every existing request path reads the full body into memory via
  `client.request(...)`; nothing bounded memory use for a large download at all.
  Caching a streamed step's result would mean trusting a stored checksum against
  disk state this run never re-verified, and a paginated or `extract`ing step's
  cached value is not the raw response shape a streamed result even produces.
- **Tradeoff:** Deliberately downloads only. A non-rewindable streaming *upload*
  (a large local file as the request body) is a separate, real feature this slice
  does not add -- request bodies remain fully-buffered typed values today, which
  are trivially safe to retry, so no new "cannot be silently retried" hazard exists
  to guard against yet. `finally`-based cleanup, not `except Exception`, because
  `asyncio.CancelledError` is a `BaseException` in this Python and a plain except
  clause would let a cancelled download's scratch file survive.
- **Evidence:** `tests/integration/test_transport.py` proves `stream_to_file`'s
  checksum and byte count against real bytes, atomicity (no scratch file survives
  success), cleanup after both a transport failure and a real `asyncio` cancellation
  (via `wait_for`'s timeout), and retry against a real flaky endpoint.
  `tests/integration/test_streaming.py` proves the SCLPLL surface end to end: a
  workflow step writes the body and reports matching metadata, a streamed step is
  never served from cache, and `paginate`/`extract` combined with `stream` are
  rejected before any request is made.

## 2026-09-07 — D7 extraction completeness signals

- **Decision:** `paginate.Follow` gains `declared: bool` and two properties:
  `items_received` (a best-effort sum of records actually received, never a claim
  about the source's real total) and `completeness` (`"complete"`, `"partial"`, or
  `"unknown"`, per SPEC section 3.7). A paginated step's result gains a
  `completeness` dict with that status plus the stop reason, page count, and item
  count. `"partial"` only when the *hard safety net* (`HARD_CEILING`, which nobody
  declared) cut the extraction short; reaching the workflow's own `max_pages`/
  `stop_when`, or a mode/CLI `--max-pages` override, is `"complete"` for that
  declared scope, because someone actually asked for exactly that. A repeated-page
  loop is `"unknown"`, since that is an anomaly neither side decided on purpose.
- **Why:** `Follow.truncated`/`reason` already existed but only reached a log line,
  never the step's own value, and did not distinguish "an explicit bound was hit"
  from "the safety net nobody asked for kicked in" -- both looked identical
  (`truncated=True`) even though only one of them means there is real data this run
  did not get.
- **Tradeoff:** While testing this, found and fixed a real pre-existing bug it
  exposed: `execute._cache_key`'s `HttpConfig` branch never included the pagination
  spec, so `max_pages=1` and `max_pages=40` against the identical URL/headers/body
  produced the *same* cache key -- a step declaring a smaller scope could silently
  read back a larger, unrelated run's cached result. `values.cache.key_for` now
  takes a `paginate` parameter fed into the hash. This is a caching-correctness fix
  more than a D7 feature, but it was a direct, load-bearing consequence of adding a
  second pagination-scope test against one server route without cache isolation.
- **Evidence:** `tests/unit/test_paginate.py` covers all three completeness
  outcomes directly, including a `HARD_CEILING` monkeypatch to trigger `"partial"`
  without fetching thousands of fake pages. `tests/integration/test_completeness.py`
  proves it through the real runner against a real paginated server route.
  `tests/unit/test_memory.py` pins the cache-key fix: two different `paginate`
  specs against the same URL now produce different keys.

## 2026-09-07 — E4 snapshots and changed test selection

- **Decision:** `sclpl test run --update-snapshots` rewrites an
  `expected_outputs` file to match what the run actually produced instead of
  failing the assertion, written atomically (scratch file + `os.replace`). The
  "did this actually change" check compares *parsed* JSON values, not raw bytes,
  so a hand-written or differently-formatted snapshot that already means the same
  thing is left alone. `sclpl test run --changed --base REF` narrows the manifest
  set to ones a `git diff --find-renames REF...HEAD` (plus `git ls-files --others
  --exclude-standard`, since untracked files never show up in a diff against HEAD)
  could plausibly affect: the manifest file itself, its fixture directory, or its
  workflow's source file. A change under a shared `functions/`/`plugins/`
  directory, or to the project manifest itself, selects every manifest rather than
  trying to trace which ones actually depend on it. No git repository, or a `git
  diff` that fails (unknown ref, git not installed), also selects everything. `test
  run` with no path argument now discovers and runs every manifest in the project
  instead of requiring exactly one.
- **Why:** Without `--update-snapshots`, adopting snapshot-style
  `expected_outputs` assertions means hand-editing JSON files after every
  intentional output change, which nobody does reliably. Without `--changed`,
  running the full test suite before every commit does not scale as a project's
  test manifests grow. Both accept criteria in the plan (E4) explicitly demand
  conservative fallbacks -- "unavailable Git base conservatively runs all" -- over
  cleverness, since a false "this test doesn't need to run" is a correctness bug
  and a false "run everything" is only a speed cost.
- **Tradeoff:** Changed-selection is path-based, not a real dependency graph: a
  workflow that dynamically references a function by name computed at runtime, or
  a fixture referenced by a relative path outside its own manifest, would not be
  detected as affected. This is deliberately conservative in the direction the
  spec asks for (shared directories always select everything) rather than
  precise. The atomic-write comparison reads back an existing snapshot file only
  to answer "did anything change"; a first-time snapshot write with no prior file
  is always treated as a real update.
- **Evidence:** `tests/unit/test_test_manifests.py` covers a mismatched snapshot
  failing with the `--update-snapshots` remedy, a successful rewrite, a no-op
  when the value already matches (parsed, not byte-for-byte), and no leftover
  scratch file after the atomic write. `tests/unit/test_test_select.py` builds a
  real git repository per test (subprocess `git`, not mocked) covering: no
  repository, an unresolvable base ref, a workflow-only change, a fixture-only
  change, an untracked fixture file, a shared-function change, a project-manifest
  change, and an unrelated change selecting nothing.
  `tests/integration/test_test_cmd.py` exercises the actual `sclpl test run` CLI
  end to end: running with no path over a project directory, `--update-snapshots`
  rewriting a real mismatch, a real mismatch failing without it, and `--changed`
  outside any git repository still running everything.

## 2026-09-07 — E6 audit and enforced policy

- **Decision:** A new, opt-in `[policy]` table on the project manifest
  (`sclpl/project/policy.py`) declares `hosts` (an allowlist, glob-matched),
  `output_roots` (paths every output must resolve under), `overwrite` (default
  `false` the moment the table exists at all), and `deny_capabilities`. Each is
  enforced exactly where its side effect would otherwise happen: hosts via an
  async `request` event hook httpx calls on every pooled client before sending
  the first request of a call *and* before every redirect it takes (`Pool.client`
  in `run/transport.py`); output roots via `Path.resolve()` against the bound
  path, in `preflight()`, independent of `--no-validate`; overwrite via a check in
  `run_workflow` right after preflight succeeds and before the output lock, the
  pool, or any step; capabilities by folding a project's `deny_capabilities` into
  the same `--deny-capability` set the CLI root callback already passes to
  `bootstrap.activate_plugins()`, which already refuses a capability before
  importing the plugin that declared it. A policy violation raises the new
  `PolicyDenied(ValidationError)` and, in the transport layer, is explicitly
  excluded from the retry loop and the circuit breaker -- it is not evidence the
  host is unhealthy, so it must not consume the retry budget or count as a
  breaker failure.
- **Why:** The plan (E6) requires that "policy denial precedes side effects and
  plugin import" and calls out path traversal, symlinks/junctions, and redirect
  escapes by name as things to verify -- three ways a naive check (compare the
  literal path or the literal request URL) would pass while the actual bytes
  still ended up somewhere the policy meant to forbid. httpx's redirect handling
  builds a new `Request` per hop and reapplies every registered hook to it before
  sending, which is what makes one hook placement cover both the URL a step wrote
  and every place a 3xx response could redirect it to. `Path.resolve()` was
  already the right primitive for output roots because C5's locking code and A1's
  project-path containment check both already lean on it for the same reason:
  the literal path string is not where a symlink, a junction, or a `..` actually
  writes.
- **Tradeoff:** This is deliberately opt-in and additive: a project with no
  `[policy]` table, or a standalone workflow with no project at all, behaves
  exactly as it did before this batch -- overwrite still silently succeeds, no
  host is refused, no output path is checked. The moment a project *does*
  declare `[policy]`, `overwrite` flips to denied by default, which is the one
  place this batch changes a default rather than only adding an opt-in
  restriction; the reasoning is that declaring `[policy]` at all is itself a
  signal the author is thinking about safety, and silently clobbering a file is
  exactly the class of thing that default should stop doing. Capability denial
  resolution happens once at CLI startup, before any subcommand (including
  `--project`) is parsed, so it can only discover a project reachable from the
  current directory -- the same constraint auth profiles and this batch's own
  `output`/`overwrite` policy already accept for a standalone invocation, not a
  new limitation this batch introduces.
- **Evidence:** `tests/unit/test_policy.py` covers parsing (defaults, an absent
  table, glob host matching, an explicit `overwrite = true`, unknown capability
  names, unknown top-level keys, wrong-typed fields) and `check_host`/
  `check_output` directly, including a `..` traversal and (skipped where the
  platform refuses an unprivileged symlink) a symlink pointing outside every
  declared root. `tests/integration/test_policy_e2e.py` proves enforcement
  through the real runner and a real local server: an allowed host succeeds, a
  disallowed one is denied, a redirect from the allowed host to the *same
  physical server* reached through a different hostname is denied (proving the
  hook fires on the redirect hop, not just the original URL), a denied request
  never reaches the server and is not retried, an output inside/outside a
  declared root is allowed/denied through the real `sclpl run` CLI, a path
  traversal through `output_roots` is denied, overwrite is denied by default
  once `[policy]` exists and can be overridden by `--overwrite` or `overwrite =
  true`, a project or standalone run with no `[policy]` table still overwrites
  as before, `sclpl project check` surfaces the resolved policy and fails
  clearly on a malformed one, and a project's `deny_capabilities` reaches
  `sclpl plugin list --refused` the same way `--deny-capability` already did.
