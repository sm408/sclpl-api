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
