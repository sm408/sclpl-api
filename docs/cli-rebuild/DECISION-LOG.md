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

## 2026-09-07 — E7 publication eligibility

- **Decision:** A new, analysis-only module (`run/eligibility.py`) derives, for
  every declared output with a writer step surviving mode pruning, its full
  upstream dependency closure in the kept plan (`derive()`), attached to
  `preflight.Report.eligibility` for a later staged-publication mechanism (E8)
  to consume. Separately, and this batch's one actual preflight failure,
  `check_stubbed_validation()` walks the *full declared* graph (not the pruned
  plan -- a pruned step has no node there at all) from every output writer and
  fails preflight when the writer's dependency chain passes through a step that
  declares `assert` and the current mode has replaced that step with a `stub`
  rather than running it.
- **Why:** SPEC batch E7's own accept criteria: "missing validation dependencies
  fail preflight." Mode resolution's existing closure check
  (`modes._check_closure`) treats a stub exactly like a kept producer or a bound
  input for the purpose of satisfying a reference -- correctly, for ordinary
  data, since that is what a stub is *for*. But a stub is a value, not a step: it
  never runs the `assert` the real step would have. A mode that stubs past an
  assertion feeding a declared output therefore ships that output's data without
  ever running the check its presence in the graph implied, and nothing before
  this batch could tell the difference between "this data was validated" and
  "this data was faked for a smaller mode" from the output's own declaration.
- **Tradeoff:** This batch's other named accept criterion -- "an assertion
  branch cannot be bypassed by a faster independent export" -- describes a
  genuinely concurrent race (an independent branch with no data dependency on
  the assertion finishing and writing before the assertion is even evaluated),
  which no static preflight check can close: closing it requires not writing
  the file until everything is known to have passed, which is a runtime,
  side-effecting change to *when* a write happens, not an analysis. That is
  deliberately left to E8, whose own accept criterion is literally "no
  destination changes before E7 passes" -- E7's job, per the plan's own batch
  boundary, is to derive what E8 needs to gate on, plus the one piece of that
  which *is* statically checkable (mode-selection bypassing validation via a
  stub), not to implement the gate itself.
- **Evidence:** `tests/unit/test_eligibility.py` covers `derive()`'s dependency
  closure and validation-scope computation directly, plus
  `check_stubbed_validation()`: a stubbed assert-bearing dependency is flagged
  naming both the stubbed step and the affected output, an unrelated stub is
  not flagged, and a workflow with no asserts at all short-circuits.
  `tests/integration/test_eligibility_e2e.py` proves it through the real
  `sclpl validate` CLI across three modes of one workflow. Building these tests
  surfaced a real, previously-untested pre-existing bug, fixed in the same
  commit: `preflight()`'s step 3 (`compile_plan`) never included a mode's
  `stub` names in the `available` set it passes to the graph builder, even
  though `resolve()`'s own closure check one step earlier does -- so *any* real
  workflow using `stub` on a value a still-kept step reads would fail preflight
  with "nothing produces it", directly contradicting the closure check that had
  just accepted the exact same reference. `stub` had only ever been exercised
  at the `modes.resolve()` unit level before this, never through the full
  `compile_plan`/`preflight()` path a real `sclpl run --mode ...` actually
  takes -- one of the new integration tests pins the fix as a named regression
  case.

## 2026-09-07 — E8 stage and publish managed outputs

- **Decision:** A project opts in with `[outputs] publish = "validated"`
  (`project/outputs.py`; absent, or no project, keeps immediate writes
  unchanged). Under it, `execute._bind_output` hands a writer step a
  same-directory scratch path (`run/publication.Ledger.stage`) instead of its
  real destination -- the step still runs on its normal schedule and produces
  its value exactly as before, only *where that value lands* changes. After the
  scheduler finishes, `runner._finish_publication` checks the run's outcome:
  `outcome.status == "ok" and not outcome.failed` publishes every staged file
  (`os.replace`, always same-filesystem) and writes a generation manifest under
  `~/.sclpl/publications/<workflow>.json`; anything else discards every staged
  file, touching no real destination at all.
- **Why:** SPEC 3.5 names the actual failure mode this has to close: "an
  assertion branch and an export branch may run independently" -- reference
  dependencies (E7's per-output `required`/`validation_scope`) cannot catch
  that, because by definition an independent branch has no reference for a
  graph walk to find. The only default SPEC 3.5 itself calls safe is "all
  selected required assertions/contracts... pass before publication" -- *all*,
  not just the ones this output happens to depend on -- which is exactly
  whole-run success. E7's per-output eligibility stays real and useful (it is
  what a later, narrower, explicitly-declared per-output scope would need to
  check for dependency closure, per SPEC 3.5's second sentence), but the
  default gate implemented here is the coarser, provably-safe one the spec
  actually asks for. Same-directory scratch paths, not a shared temp root,
  because `os.replace` is only atomic within one filesystem, and a path's own
  directory is the one place guaranteed to share it with its destination --
  this also means "cross-filesystem rejection" never has to be handled as a
  special case, because the scratch file is never anywhere it could apply.
- **Tradeoff:** Explicitly out of scope for this slice, called out rather than
  silently missing: validated stdout publication (SPEC 3.5's "stdout spooling
  limits" needs a bounded spool file and a hold-until-validated print, which is
  its own mechanism; stdout stays immediate even under `publish = "validated"`)
  and SQLite's short-transaction-with-rollback requirement (the bundled sqlite
  plugin writes its `.db` file directly, so this batch's atomic rename does
  cover that file once the plugin's own write call returns, but does not add a
  SQL-level transaction boundary inside that call, and no attempt was made to
  reach into a separate plugin's connector to add one). A manifest lives at a
  fixed per-workflow path (last generation only, not a history); "publish an
  immutable output generation" in SPEC 3.5's stronger sense (multiple retained
  generations, an all-or-nothing manifest *pointer* swap across them) is a
  larger feature this establishes the primitive for rather than delivers whole.
- **Evidence:** `tests/unit/test_publication.py` covers staging (same-directory,
  idempotent per port across retries), atomic publish, the generation manifest
  (written only when something was actually published, naming every published
  port), discard leaving a prior destination untouched, and a failed
  `os.replace` reported as `interrupted` rather than silently dropped.
  `tests/unit/test_outputs.py` covers `[outputs]` parsing. `tests/integration/
  test_publication_e2e.py` proves the actual accept criterion through the real
  `sclpl run` CLI: immediate mode is unaffected by no `[outputs]` table at all;
  validated publication produces the real file with no scratch file left behind
  on success; a failing run leaves neither a scratch file nor a destination
  file; a second, failing run does not touch what a first, successful run
  already published ("preserve the last valid output when validation fails");
  a generation manifest is written naming the published file; and -- the test
  that matters -- a writer step with *no data dependency at all* on a failing
  `assert` step in the same workflow still does not get its file published,
  because the run as a whole failed.

## 2026-09-07 — E9 verify format fidelity

- **Decision:** Two round-trip bugs found by testing every named case (leading
  zeros, large ids, decimals, timezone-aware timestamps, nulls, empty tables)
  against every format were fixed in `tables/pandas_backend.py`. CSV: before
  `pandas.read_csv` sees the file, its raw text is scanned for any column
  holding a value matching `^0\d+$` (a leading zero followed by more digits --
  the one shape no ordinary number has) and that column is forced to
  `dtype=str`, so `00123` survives as `"00123"` instead of becoming the
  integer `123`. Excel: before `to_excel` is called, every column is scanned
  for an integer whose magnitude exceeds `2**53` (the largest integer an
  IEEE-754 double -- all a number is, in Excel -- can represent exactly); if
  one exists, the write is refused with a diagnostic naming the column and the
  exact value, rather than writing a silently different number. A pre-existing
  `to_excel` refusal on a timezone-aware column is now caught and re-raised as
  an `sclpl` `ValidationError` with a remedy, instead of a raw pandas
  `ValueError`. Reading an empty-table CSV's pandas `EmptyDataError` is now a
  named `ValidationError` explaining that a zero-row CSV has no header row to
  infer columns from -- CSV's own real limit, not something this batch can fix,
  only explain clearly.
- **Why:** SPEC E9's accept criteria name these exact cases and give two
  acceptable outcomes: "retain declared meaning or fail with a loss
  diagnostic." A probe script (not committed; its findings are what the new
  tests pin) round-tripped every named case through every format before any
  fix existed. JSON, NDJSON, and Parquet already retained everything correctly
  -- Parquet even keeps `Decimal` and timezone-aware `Timestamp` as real typed
  values, and JSON/NDJSON represent a `Decimal` as its exact decimal text,
  which is the closest either format can get to a type neither one has
  natively. CSV's leading-zero loss and Excel's large-integer corruption were
  the two cases actually failing the accept criterion: both were *silent* --
  a different, shorter value with no error at all, which is the one outcome
  SPEC E9 does not allow.
- **Tradeoff:** SQLite is explicitly out of scope for this batch: it writes
  through a separate bundled plugin (`plugins_bundled/sqlite`) that never goes
  through `tables/io.py`, so nothing here touches it. The leading-zero
  protection is a heuristic on the *shape* of the raw text, not a declared
  schema -- a column of real integers that happen to all start with a
  coincidental `0` (vanishingly rare, since a real leading zero on a
  non-padded number is not how integers are written) would also be protected,
  which costs nothing since the exact same text still reads back correctly as
  a string. The Excel large-integer check inspects the DataFrame's actual
  values before writing, not a static schema, so it costs a full column scan
  per write -- accepted for Excel exports, which are not the hot path large
  extractions choose.
- **Evidence:** `tests/unit/test_format_fidelity.py` covers every named case
  against every format it applies to: a leading-zero string surviving CSV
  (both self-produced and a hand-written CSV this project never wrote), a bare
  `0` and a leading-zero decimal (`0.5`) confirmed *not* protected since
  neither is ambiguous, a large integer exact through JSON/NDJSON/Parquet/CSV,
  a too-large integer refused for Excel with the pre-fix corrupted value named
  in the test's own docstring as what used to happen silently, a
  timezone-aware timestamp refused for Excel with a remedy and kept exact
  through NDJSON/Parquet, a decimal's exact text preserved everywhere it
  cannot keep the type, nulls surviving as `None` rather than a string or NaN,
  and an empty table round-tripping as zero rows everywhere except CSV, where
  it now fails with a named, clear diagnostic instead of a confusing internal
  pandas one.

## 2026-09-08 — F1 complete event measurements

- **Decision:** `state/db.py`'s schema already carried columns for
  `run_steps.attempts`/`duration_ms`/`cached`/`lane` and
  `runs.bytes_in`/`bytes_out`/`retries`; `runner._remember` simply never wrote
  to them. A new `execute.Runtime.metrics: dict[str, StepMetrics]`, keyed by
  graph node id, accumulates HTTP attempts and response bytes as `_http`
  issues each request (including every page of a paginated step) and marks a
  cache hit in `run_step`. `schedule.Outcome` gained `step_durations` and
  `step_lanes`, populated in `_execute` at the same three points it already
  builds the live `StepFinished` event, so history gets the same numbers a
  live run showed rather than re-deriving them. `_remember` now builds each
  `StepRecord` from `outcome`/`runtime` instead of the schema's bare defaults,
  and sums `bytes_in`/retries (attempts beyond the first, summed per step)
  onto the `RunRecord`.
- **Why:** SPEC F1's accept criterion is specific and checkable: "report
  counts reconcile with observed local-server requests." Before this, every
  persisted run showed `attempts=1` and `duration_ms=0` for every step
  regardless of how many times it actually retried or how long it actually
  took -- the columns were there, but nothing had ever been asked to look
  correct against a real server, because nothing wrote real numbers into them.
  Metrics are keyed by graph node id rather than the step's own id because a
  loop's iterations share one step definition but are separate nodes with
  separate HTTP activity; keying by step id would have merged an iteration's
  attempts into its siblings'.
- **Tradeoff:** `bytes_out` (request bytes sent) is not populated -- see the
  regression below -- and stays at the schema's existing `0` default rather
  than a guessed or partial number. Attempt counts are graph-node-scoped, so a
  step that shares work across control-flow copies in ways not modeled as
  separate nodes would not be reflected exactly right; this covers the actual
  node structure the scheduler and `StepFinished` already use, not a
  reinterpretation of it.
- **Evidence:** A real, previously-passing test broke while building this:
  `test_auth_does_not_survive_a_cross_origin_redirect` started failing with
  httpx's `RequestNotRead` because the first version of this change read
  `response.request.content` to count bytes sent, and a GET's body stream is
  never marked read -- accessing it raises rather than returning an empty
  byte string. Fixed by dropping bytes-sent accounting entirely rather than
  guarding it defensively, since `response.content` (bytes received) is
  always safely readable by the time a non-streaming request returns and
  bytes-sent was the smaller, riskier claim of the two.
  `tests/integration/test_run_metrics_e2e.py` proves the actual accept
  criterion through the real `sclpl run` CLI and the local test server's own
  `ATTEMPTS` counter (`tests/integration/conftest.py`): a step retried against
  `/flaky/2` persists `attempts == 3`, matching the server's own count exactly,
  with a real nonzero `duration_ms` and the correct lane; a second run against
  an already-cached URL persists `cached=true` and `attempts == 1`; and a run
  with one retry sums to `retries == 1` and a nonzero `bytes_in` on the
  `RunRecord`. `tests/unit/test_runner.py`'s two existing `_remember` tests
  were updated for the new required `runtime` parameter, unchanged otherwise.

## 2026-09-08 — F2 reports and comparisons

- **Decision:** A new `render/report.py` renders one recorded run three ways
  from the same data (`render_text`, `render_json`, `render_html`), wired to
  a new `sclpl runs report <run> [--format text|json|html] [--into path]`
  command. HTML is self-contained: inline `<style>` only, no `<script>` tag,
  no external stylesheet or CDN reference, and every value that could carry
  arbitrary text from a response body -- a step's error message above all --
  is passed through `html.escape` before it reaches the page. `db.compatible
  (left, right)` checks two runs share a workflow and environment; `runs
  diff` prints a note when they do not, rather than silently producing a
  diff between two unrelated things.
- **Why:** SPEC F2's accept criteria, taken directly: reports "need no
  external scripts/assets" (an HTML report is meant to be opened as a local
  file or attached to a bug report, and a page that phones out or executes
  is not that), and "malicious response strings" must not become live markup
  in a rendered report -- a step's error text routinely echoes a server's
  own response body, which is attacker-controlled the moment the server is.
  "Compare compatible runs by workflow/environment/identity" is the second
  half `runs diff` was missing entirely: it already diffed any two rows
  found by id or name with no opinion on whether comparing them meant
  anything.
- **Tradeoff:** "Old runs show unknown measurements rather than fabricated
  zeros" is honored only where it can actually be told apart from real data:
  `duration_ms` left at the schema's default (`0`) renders as unknown,
  because no real request takes exactly zero milliseconds. `attempts` does
  not get the same treatment -- its own unmeasured default is `1`, which is
  also the ordinary value for a real step that succeeded on the first try,
  so a stored `1` cannot be told apart from a genuine one. Reporting it as
  "unknown" every time would be just as dishonest as reporting a fabricated
  measurement; the module docstring and a code comment say so, rather than
  silently claiming full coverage of the accept criterion. "Selector ties"
  needed no new code: `History.find` already lists candidates rather than
  guessing on an ambiguous id/name prefix.
- **Evidence:** `tests/unit/test_report.py` covers all three renderers
  directly against an in-memory SQLite table shaped like the real schema: a
  real measurement and a zero-duration "old row" render differently, JSON
  output round-trips through `json.dumps`, and HTML escapes both a
  script-injection attempt in a step's error and in the run's own name, with
  no `<script>` tag or external URL anywhere in the page.
  `tests/integration/test_report_e2e.py` proves the same through the real
  `sclpl runs report`/`sclpl runs diff` CLI: text and JSON formats carry the
  real workflow/status/step data, an HTML report written with `--into` has a
  title and no script or external reference, diffing two different workflows
  prints the incompatibility note, and diffing two runs of the same workflow
  does not.

## 2026-09-08 — F3 output lineage

- **Decision:** `run_ports.digest` -- a column that already existed in the
  schema, always written `""` -- now holds a real SHA256 of each bound
  file's actual bytes (`state/db.file_digest`, chunked so a large output is
  never held whole in memory), computed for every input and output port with
  a real single path once `_remember` runs. `History.producers_of(path)`
  (new) finds every run recorded as having produced a given output path,
  most recent first, compared through the same `canonical_path` (resolved,
  case-folded on Windows) that C5's output locking already established --
  reused rather than reimplemented, so the two features agree about what
  "the same file" means. `sclpl runs which <path>` (new; `cli/`'s budget
  raised 1,800 to 2,000 in [ADR 0007](../adr/0007-budget-cli-for-batch-f-reporting.md)
  to fit it) reports every producing run, flags more than one as ambiguity
  rather than silently choosing the most recent, and compares the recorded
  digest against the file's current bytes to report a later modification.
- **Why:** SPEC F3's accept criterion, almost verbatim: "output-path lookup
  resolves the producing run/digest and reports ambiguity or later
  modification." The digest has to be of the file's actual on-disk bytes,
  not the in-memory value that produced it, because "has this changed since"
  is a question about the file, and only re-hashing the file can answer it
  independently of what the run itself remembers. For a validated-publication
  run (E8), the digest is computed after `_finish_publication` has already
  moved the staged file to its real destination, so it fingerprints what a
  reader of that path actually sees, not a scratch file that may not even
  exist by the time anyone looks.
- **Tradeoff:** Digesting is scoped to a binding's *first* bound path
  (`Binding.path`), matching the existing `describe()` behavior for a
  multi-file glob binding ("N files" is not a real path either) -- lineage
  for the rest of a glob's files is not tracked in this slice. Path matching
  is done by fetching every recorded output port and filtering in Python
  with `canonical_path`, not a SQL-side comparison; correct and simple for a
  local, small-scale history database, and consistent with how `History`
  already does everything else (`find`'s prefix search, `search`'s text
  match) -- not built to scale past what a personal run history actually is.
- **Evidence:** `tests/unit/test_lineage.py` covers `file_digest` (a real
  SHA256, empty for a missing file, changes when the bytes change) and
  `producers_of` directly against a real `db.History` (finds the recorded
  producer, matches a relative and an absolute spelling of the same path,
  returns nothing for an unrelated path, lists every match most-recent-first
  when more than one run claims the same path, and ignores input-direction
  ports entirely). `tests/integration/test_lineage_e2e.py` proves it through
  the real CLI: `sclpl runs which` resolves the producing run with no false
  warning, flags a hand-edited file as modified since, reports "ambiguous: 2
  runs" when the same workflow writes the same path twice naming both runs,
  and fails clearly on a path no run ever produced.

## 2026-09-08 — F4 retention consistency

- **Decision:** `History`'s SQLite connection now sets `PRAGMA
  journal_mode=WAL` once, at construction. Three new tests pin what was
  already true rather than changing behavior: pruning down to `keep=1`
  leaves a survivor's row, tags, ports (with their digest), steps (with
  their attempts), and NDJSON log completely untouched; a crashed run left
  at `status="running"` (what `_remember_start` writes before a single step
  executes, if the process never reaches the matching `_remember`) prunes
  like any other row instead of getting stuck; and a second `History`
  connection can read while a first still holds the database open.
- **Why:** SPEC F4's accept criterion is "pruning one run cannot break
  another retained run," and its own verify list names concurrent readers
  and crash leftovers directly. Auditing what the codebase actually shares
  across runs today turned up nothing: no shared blob store, no
  reference-counted artifact, nothing `_forget` could delete out from under
  a survivor even by accident -- each run's NDJSON log is uniquely named by
  its own id, and every `_forget(identifier)` call only ever touches rows
  and a file scoped to that one id. The genuine gap was narrower than the
  batch name suggests: without WAL, SQLite's default rollback-journal mode
  can make a reader wait on (or fail against) a writer's lock, which is
  exactly the "concurrent readers" case named in the verify list.
- **Tradeoff:** Storage quotas, checkpoint-root protection, and
  notification-reference protection are explicitly out of scope, not
  silently missing: no quota mechanism exists anywhere in the codebase to
  enforce, and checkpoints (G1) and notifications (I-batch) have not been
  built yet, so there is nothing yet for retention to respect there. This is
  the same "foundation now, extend when the dependency lands" scoping this
  plan has already used for E5, E9's SQLite path, and E8's stdout spooling.
- **Evidence:** `tests/unit/test_state.py` gained three tests:
  `test_pruning_leaves_every_row_of_a_surviving_run_untouched` (a survivor's
  data checked across `runs`, `run_tags`, `run_ports`, `run_steps`, and its
  log file, not just the top-level row), `test_a_crashed_run_left_at_status_
  running_is_pruned_like_any_other_row`, and `test_a_reader_is_not_blocked_
  by_a_writer_in_wal_mode`. The full existing `test_state.py` suite (34
  tests, including the pre-existing pin/prune coverage) and the full project
  suite both still pass unchanged.

## 2026-09-08 — F5 partial-result reporting and automation

- **Decision:** Two new persisted columns, `runs.completeness` and
  `runs.publication`, added through a genuinely incremental schema migration:
  `state/migrations.py`'s `migrate()` gained an `upgrades: dict[int, str]`
  parameter, applied after the base schema and only for versions the database
  has not already reached, because `CREATE TABLE IF NOT EXISTS` (the base
  schema's own idempotency mechanism) is a no-op for a table that already
  exists -- it can never add a column an earlier version of this project
  never wrote. `db._UPGRADES = {2: "ALTER TABLE runs ADD COLUMN ..."}` is the
  actual SQL, kept in `db.py` rather than the generic `migrations.py` module,
  which stays schema-agnostic (its own test suite already exercised it with
  an arbitrary, unrelated schema, which is what caught the first version of
  this change hardcoding `runs`-specific SQL into the wrong layer).
  `execute.Runtime.completeness` collects every paginated step's own D7
  `completeness.status` as it runs; `runner._completeness_of` reduces the
  list plus cancellation to the run's overall verdict ("unknown" > "partial"
  > "complete"). `runner._finish_publication` (E8) now returns
  `"published"`/`"interrupted"`/`"withheld"` instead of only logging.
  `Options.require_complete` (`--require-complete`) turns a would-be exit 0
  into the new `EXIT_INCOMPLETE` (7) when completeness is not `"complete"`.
  `render/report.py`'s three formats all surface both fields plainly.
- **Why:** SPEC F5's accept criteria, essentially verbatim: human/JSON/HTML
  output must not label partial data as complete, and `--require-complete`
  follows section 3.7's exit rules ("fails validation when completeness is
  partial/unknown without another failure code"). Completeness is aggregated
  over the *whole run*, not scoped to one output's own dependency closure
  (unlike E7's per-output `validation_scope`), because SPEC 3.7 states the
  rule at the run level -- "record execution status separately from data
  completeness" -- and a step whose own extraction was cut short is real
  missing data regardless of which output, if any, downstream of it actually
  reads its value.
- **Tradeoff:** JUnit output is explicitly out of scope: no such renderer
  exists anywhere in this codebase, and adding one is a new format to build,
  not a wiring task like the rest of this batch was. Carrying completeness/
  publication through checkpoints and notifications is not done either --
  neither system exists yet (G1, I-batch) -- nor into cache entries, which
  SPEC 3.7 also names ("partial cache data must never satisfy a complete-data
  requirement without revalidation") but which is a real, separate change to
  `values/cache.py`'s own read path, not a field this batch's history/report
  surface could carry on its own. `require_complete`'s check runs once, after
  the whole scheduler finishes and before `_remember`, using the exact same
  `_completeness_of` call `_remember` itself uses -- computed twice rather
  than threaded through as a parameter, a deliberate, low-risk simplicity
  trade since the inputs cannot have changed between the two call sites.
- **Evidence:** `tests/unit/test_migrations.py` gained three tests proving
  the incremental-upgrade mechanism itself: a hand-built version-1 database
  reaches version 2 with the new columns and its existing row intact, a
  database already at the target version does not re-apply (which would
  otherwise fail with "duplicate column"), and the project's own real
  `db._UPGRADES` produce the expected defaults through an actual `History`
  open. `tests/unit/test_completeness.py` covers `_completeness_of`'s
  aggregation directly (no paginated steps, all complete, one partial, one
  unknown, unknown outranking partial, and cancellation forcing unknown even
  with no paginated step or even a step reporting complete).
  `tests/unit/test_report.py` proves a `status: "ok"` run with
  `completeness: "partial"`/`"unknown"` is never rendered as complete in any
  of the three formats, and that publication state appears when declared and
  stays quiet at its `"n/a"` default. `tests/integration/
  test_require_complete_e2e.py` proves the real behavior end to end: a fully
  complete run is unaffected by `--require-complete`; a partial run (the real
  `/paged` server route, `paginate.HARD_CEILING` lowered the same way
  `test_paginate.py`'s own unit tests already do, since the real 10,000-page
  ceiling cannot be exercised in a real integration test) exits
  `EXIT_INCOMPLETE` only when the flag is set, and exits 0 without it; a
  step's real assertion failure keeps its own exit code even with the flag
  on; and an ordinary run's `completeness`/`publication` reach the real
  history database through the real CLI, not just the in-process `Result`
  the other tests check.

## 2026-09-08 — G1 durable checkpoints

- **Decision:** New `run/checkpoints.py` module, a `Store` with its own
  SQLite database (`checkpoints.db`, separate from `history.db`) plus a
  blob directory. `write(run_id, step_id, value)` is two-phase: write the
  value to a scratch file beside its final name, `os.replace()` it into
  place (cleanup of the scratch file happens in a `finally`, since
  cancellation is a `BaseException` a plain `except Exception` would miss),
  and only after that succeeds does an `INSERT OR REPLACE` commit the
  metadata row. `read(run_id, step_id)` looks up the row, then re-hashes the
  blob against the digest recorded at write time before trusting it --
  file missing or changed since means `None`, the same as never having been
  checkpointed. Only `Table` (Parquet) and strict-JSON-eligible values
  (`json.dumps` with no `default=`) are checkpointed; everything else makes
  `write()` return `None` rather than raise or invent a lossy encoding.
- **Why:** the plan's own G1 accept criterion is that a checkpoint is
  reusable "only after its blobs and metadata are durably committed" and
  must survive "process termination before/after each persistence
  boundary." Ordering the blob rename before the DB commit means the only
  possible crash-window outcome is an orphaned blob with no row naming it --
  which `read()` never sees, since it only ever consults the metadata table,
  never the filesystem directly -- not a row pointing at a blob that was
  never finished. Re-verifying the digest on every `read()` (not just
  trusting a committed row) closes the remaining gap: a row can be durable
  and correct at commit time and still stop being trustworthy later, if
  something outside this module's control touches the file afterward.
- **Tradeoff:** G1 ships as a standalone, currently-uncalled library.
  Nothing in `runner.py` or `execute.py` invokes `Store.write()`/`read()`
  yet -- that wiring, plus deciding which completed steps are even eligible
  to resume from (a step whose completeness was itself `"partial"`, per
  F5, should not silently be treated as reusable) is G2's job, kept as a
  separate slice so this module's own durability contract can be tested in
  isolation first, before anything depends on it.
- **Evidence:** `tests/unit/test_checkpoints.py`, 14 tests: eligibility
  (dict/Table eligible, set/arbitrary object not), exact round-trip for
  both JSON and Parquet, an unsupported value never produces a blob or row,
  reading a step that was never written is a clean `None`, writing twice
  replaces the prior checkpoint, a blob written to disk with no committed
  row is not reusable (the literal "died mid-write" case), no scratch file
  survives a successful write, a blob tampered with or deleted after being
  checkpointed is rejected on read (digest mismatch), and `discard()`
  removes both the rows and the blob files for a run without touching
  another run's checkpoints. Full project suite: 1037 passed, 2 skipped
  (unchanged, pre-existing) -- zero regressions.

## 2026-09-08 — G2 resume eligibility planning

- **Decision:** New `run/resume.py::plan_resume()` decides, for every step of a
  workflow's static plan, whether a prior run's checkpoint is `"reuse"`-able,
  must `"rerun"`, or is `"refuse"`d pending an explicit recovery decision --
  without executing a single step. Two comparisons do all the work. First,
  identity: `run_steps` gained a persisted `identity_key` column (the exact
  digest `execute._cache_key` computed when the step actually ran, saved via a
  new `runtime.identity_keys` dict populated in `run_step()`); a candidate run
  recomputes the same function, for real, against its own current `vars`/inputs
  and (for a step reading another step's output) the ancestor's rehydrated
  checkpoint value, and compares. Second, propagation: a step's verdict can never
  be `"reuse"` unless every step it structurally depends on is *also* `"reuse"`,
  checked once per node in topological order rather than re-derived per case.
  Non-idempotent HTTP writes get a third outcome: `"refuse"`, when the prior
  attempt's own outcome is not confirmed-successful (failed, drifted, or its
  checkpoint is gone) -- silently rerunning would risk repeating a side effect
  that may have already reached the server. `checkpoints.Store` gained
  `exists()`, a cheap integrity check that never deserializes a checkpoint's
  blob, because `read()` alone cannot tell "nothing was ever checkpointed" apart
  from "the checkpointed value actually was JSON `null`".
- **Why:** SPEC's G2 accept criteria almost verbatim: "dry-run explains reuse/
  rerun/refusal for every step; drift and missing artifacts invalidate affected
  steps and descendants." Reusing `execute._cache_key` directly, rather than
  reimplementing an approximation of interpolation/hashing inside `resume.py`,
  was a deliberate choice after noticing the alternative (compare declared IR
  shape, then separately guess whether resolved values match) would either miss
  real drift (an unchanged step definition fed a changed `--var`) or duplicate
  logic that already exists and is already tested -- the session's standing
  instruction to verify before writing rather than build two versions of the
  same idea. The one real design gap this surfaced: `_cache_key` returns `None`
  whenever `Runtime.cache` is `None`, since a real run only ever computes an
  identity key to decide whether *its own* response cache has a hit -- so
  `plan_resume` opens a real (default-policy) `values.cache.Cache` purely to
  satisfy that gate, never reading or writing an entry through it. This is
  intentional, not incidental: a run executed with `--no-cache` would never have
  populated `identity_keys` for any step either, so nothing from it is
  checkpoint-eligible in the first place -- checkpoint reuse is an extension of
  the same "this step's result is safely reusable" concept the cache already
  embodies, not a separate one.
- **Tradeoff:** Dynamic control flow (`foreach`/`while`/`if`/`parallel`/`gate`/
  `use`) is a single opaque node in the *static* plan -- its per-iteration copies
  don't exist until the loop actually runs (`compile_plan.py`'s own docstring:
  "a nested body step is not a node... it becomes one when its parent runs") --
  so such a node, and everything statically downstream of it, always plans as
  `"rerun"` here. Per-iteration reuse inside a loop is left entirely to G3, which
  can check each real iteration's own checkpoint once it actually re-expands the
  loop and knows its concrete iteration keys; guessing them here, before any
  execution, would be exactly the kind of speculative correctness this module
  exists to avoid. `let` and other pure local steps are treated the same as
  control flow (never checkpointed, since `_cache_key` only ever returns a key
  for `http`/`fn` kinds) -- correct rather than merely simple, since G1 itself
  never checkpoints anything else, but it does mean a step chained after a `let`
  can never satisfy "every ancestor reuses," even though recomputing a `let` is
  free. Accepted rather than special-cased, since the cost is one cheap local
  recomputation, never a real request.
- **Evidence:** `tests/unit/test_resume.py`, 13 tests built on a workflow
  constructed directly from the IR (no parser needed) plus a real, tmp-scoped
  `db.History`/`checkpoints.Store`/`values.cache.Cache` standing in for "what a
  prior run actually left behind": an unchanged leaf step and an unchanged
  dependent step (once its ancestor's checkpoint is rehydrated) both reuse; a
  step with no prior record, and a step whose identity matches but has no valid
  checkpoint, both rerun; a changed resolved input (a `--var` value, not the
  step's own declared config) is caught as drift; that drift propagates to force
  an idempotent dependent to rerun and a non-idempotent dependent write to
  refuse; a non-idempotent write with no successful prior attempt is refused,
  the identical write that already succeeded is reused (never repeated), and a
  step explicitly marked `retry.idempotent` is never refused regardless of its
  prior outcome; control flow always reruns; a different workflow name refuses
  every step's reuse outright. Full project suite: 1050 passed, 2 skipped
  (unchanged) -- zero regressions. A real end-to-end smoke test (`sclpl run`
  against an unreachable host, then `sclpl runs resume-plan` against the
  resulting failed run) confirmed the actual CLI wiring, not just the unit
  tests: `smoke resumed from <id>: 0 reuse, 1 rerun, 0 refuse` /
  `a  rerun  prior attempt did not succeed (failed)`.

## 2026-09-08 — G3 resume execution

- **Decision:** `sclpl run --resume-from RUN [--force-resume STEP ...]` performs
  a real resume. `run_workflow` calls the new `_resume()` helper (own
  short-lived `db.History`/`checkpoints.Store`/`values.cache.Cache` handles,
  separate from the run's real ones) right after preflight succeeds -- before
  `_remember_start`, at the same phase as the pre-existing overwrite-denial
  check -- so a refusal touches nothing that needs undoing: no history row, no
  output lock, no connection. On success, every `"reuse"`-verdict step's
  checkpointed value becomes a stub (the same mechanism `report.resolved.stubs`
  already uses for a mode-pruned producer), and the plan actually handed to the
  `Scheduler` is `report.plan.subgraph(kept)` with those nodes removed, so a
  reused step is never scheduled -- not raced, not skipped at the last moment,
  simply never a node in the graph the scheduler sees. The new run's own
  `runs.parent_run_id` links it back. Two prerequisite gaps, both real and
  neither visible until execution (not just planning) was wired up: `execute.py`
  now actually calls `checkpoint_store.write()` for every cacheable step's
  value (`Runtime.checkpoint_store`/`run_id`, new fields, gated on
  `options.record` the same way history itself is) -- without this, G1/G2 had
  no runtime that ever produced a checkpoint to resume from; and
  `checkpoints.py`'s blob filename now sanitizes a step id before using it as a
  path component, because a dynamic loop's real node id contains `control.MARK`
  (`"::"`), which is not a valid filename on Windows.
- **Why:** SPEC's G3 accept criteria: "a successful durable export is not
  duplicated; an uncertain non-idempotent HTTP write is refused without an
  explicit safe recovery policy." The refusal check running before any side
  effect (matching the existing overwrite-check's own placement, not inventing
  a new phase) is what makes "touched nothing that needs undoing" literally
  true rather than a rollback promise. `--force-resume` is per-step rather than
  a single blanket flag on purpose: SPEC says "explicit... policy," and a flag
  that silences every refusal in one pass would let an operator wave through a
  write they never actually looked at.
- **Tradeoff:** a reused step's own `assert` is not re-verified against
  today's workflow -- inherited from mode-pruning's stub mechanism (already
  documented there, in `eligibility.check_stubbed_validation`'s own docstring),
  not a new gap this batch introduces; closing it for stubs generally is
  validation-layer work, not an execution-path concern. A resumed run's overall
  `completeness` is capped at the parent's own recorded value whenever anything
  was reused, rather than tracked per reused step (`run_steps` has no
  per-step completeness column -- only the run-level aggregate F5 already
  persists) -- a conservative, honest approximation: a step's data that was
  never re-extracted this run cannot be *more* complete than it already was,
  even though this occasionally overstates incompleteness when the reused step
  itself was actually complete but a *different* step in the parent run was the
  partial one. G4 (publication state recovery specifically -- generation
  identifiers, completion receipts, destination-digest validation under C5
  locks, ambiguous fixed-path multi-output commits) is not started.
- **Evidence:** `tests/unit/test_resume_execution.py`, 5 tests against
  `runner._resume()` directly: a partial parent caps the resumed run's own
  completeness, a complete parent adds no penalty, the executed plan is
  correctly pruned to exclude reused nodes (with the reused value present as a
  stub), a refusal names the step and points at `--force-resume`, and
  `--force-resume` lifts a refusal (the step then simply reruns as an ordinary
  miss). `tests/unit/test_checkpoints.py` gained a regression test pinning the
  Windows-filename fix directly (`"details::0::one"` round-trips, and its blob
  filename contains no `:`). `tests/integration/test_resume_e2e.py`, 3 tests
  through the real CLI end to end: a real failed run's succeeded step is never
  re-fetched on `--resume-from` (`--no-cache` on the second attempt rules out
  the ordinary response cache as the explanation), an unrelated workflow name
  reruns everything with an honest "0 reused," and a non-idempotent write with
  no confirmed-successful prior attempt blocks the resume entirely (no history
  row for the blocked attempt at all) until `--force-resume` explicitly
  acknowledges it. Full project suite: 1059 passed, 2 skipped (unchanged) --
  zero regressions, including after the Windows-filename fix (which two
  pre-existing, previously-passing integration tests caught immediately once
  checkpoint writes went live on a real dynamic-loop workflow).
