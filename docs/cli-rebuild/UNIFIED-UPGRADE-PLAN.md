# sclpl unified upgrade: v1.1 + v2.0 + v2.1

Status: proposed implementation plan; no product changes implemented by this document.
Repository baseline inspected: 2026-09-05. Target: one integrated v2.1 release and one
final squash commit, with independently verified implementation batches.

## 1. Outcome and scope

Deliver the complete CLI journey: initialize a project, import an API request, select
an environment, validate and lock its dependencies, record sanitized fixtures, test
contracts offline, execute reliably, inspect reports and lineage, resume eligible
failed runs, and distribute the project through a team-owned registry.

Combine the three proposed releases by subsystem. Build configuration, identity,
transport interception, artifact storage, and run events once; make all dependent
features consume them. Do not implement three generations of the same infrastructure.

The release includes the union of the detailed v2.0/v2.1 sections and the recommended
v1.1/v2.0/v2.1 release lists. This deliberately includes notifications, failed-run
resume, shared package distribution, CI integration, OpenAPI/Postman import, and policy
controls. It also includes the stronger HTTP and authentication requirements.

Scheduling, hosted execution, dashboards, accounts, shared-secret hosting, billing,
SSO, a marketplace, visual editing, Kubernetes, AI generation, and a TUI remain outside
this upgrade. Insomnia import is a later adapter, not a release blocker. JSON Schema
is supported for contracts; arbitrary mapping-format import requires a separately
defined source format and is outside this release.

The installed package currently declares `0.1.0`. Product release numbers, SCLPLL v2,
the workflow's own `version`, plugin API versions, and persistence schema versions
are separate concepts. Publish directly as `2.1.0` after the integrated acceptance
gates; do not manufacture intermediate releases or tie language version to package version.

## 2. Repository findings that change the implementation order

| Existing foundation | Evidence | Upgrade action |
|---|---|---|
| Typed workflow, parser, reference DAG, preflight | `sclpl/run/ir.py`, `compile_json.py`, `sclpll/`, `preflight.py`, `plan.py` | Extend one compilation path for execution, testing, lint, graph, and import validation |
| Central workflow orchestration | `sclpl/run/runner.py`, `execute.py`, `schedule.py` | Inject resolved project context and shared services; retain the scheduler |
| Pooling, retries, adaptive limits, circuit breakers | `sclpl/run/transport.py`, `retry.py` | Complete policy wiring and transport behavior; do not build a replacement HTTP client |
| HTTP cache validators, incomplete revalidation | `sclpl/values/cache.py`, `docs/limitations.md` | Add conditional requests and correct cache partitioning |
| Assertions and typed errors | `sclpl/functions/diagnostics.py`, `sclpl/errors.py` | Share assertion evaluation with contracts and workflow tests |
| History, exports, diffs, NDJSON events | `sclpl/state/db.py`, `sclpl/render/events.py`, `sclpl/cli/admin_cmd.py` | Add provenance, complete measurements, migrations, checkpoints, and reports |
| Secret environments and reporter redaction | `sclpl/state/secrets.py`, `sclpl/render/redact.py` | Extend to project profiles and every persistence/output boundary |
| Plugin manifest/API/capability checks | `sclpl/ext/plugins.py`, `sclpl/ext/api.py` | Separate discovery from import; verify project policy and locks before executing plugin code |
| CLI imports plugins during module initialization | `sclpl/cli/app.py` | Move policy/context resolution before plugin activation |
| Catalogue `import`, `list`, `show`, `remove` | `sclpl/cli/catalog_cmd.py` | Preserve syntax while introducing source-format adapters |
| `runs replay` prints a prior command | `sclpl/cli/admin_cmd.py` | Preserve it; offline replay gets explicit transport options and workflow commands |
| Budget and documentation gates | `scripts/check_budget.py`, `check_layering.py`, `check_vault.py`, `cli/docs_cmd.py` | Budget new packages explicitly and wire every documented gate into CI |

Measured budget baseline: 12,253 counted code lines of 16,000 total. CLI headroom is
69 lines; runner headroom is 335. The upgrade cannot reasonably fit unchanged budgets.
Record a justified budget ADR and revise SPEC section 19 before expanding code. Do
not bypass counting by placing new code in unbudgeted packages. Improve the budget
checker to reject unlisted packages. The current layering checker detects reciprocal
package edges, not all longer cycles; extend it to detect arbitrary directed cycles.

The checked-in CI currently runs Ubuntu with Python 3.11 and 3.13 and gates lint,
formatting, types, tests, and budgets. Layering, vault, generated-doc drift, executable
examples, and cross-platform coverage need explicit jobs or steps; README claims are
not proof that those gates run. Baseline tests were not executed for this planning task.

## 3. Architecture decisions to settle once

### 3.1 Project context and precedence

Use one immutable resolved context for CLI execution, calls, tests, contracts, replay,
packages, and resume. It contains project root, selected environment, effective
nonsecret settings, secret handles, plugin inventory, policy, and execution identity.

Project discovery walks upward to the nearest `sclpl.toml`; `--project PATH` overrides
discovery. Existing standalone files and catalogue workflows still work without a
project. Project-relative paths resolve against the manifest root, never an incidental
working directory. Reject ambiguous workflow names and explain resolution provenance.

Ordinary setting precedence, lowest to highest: built-in defaults, user defaults,
project defaults, environment overlay, workflow settings, selected mode, explicit CLI
overrides. Preserve existing mode/CLI behavior. Environment selection is explicit
`--env`, then `SCLPL_ENV`, then locally selected environment, then project default.
Security policy is intersected across sources: a CLI flag cannot relax an enforced
project policy. `project check --json` explains effective values without secrets.

Proposed project layout:

```text
my-integration/
  sclpl.toml
  sclpl.lock
  workflows/orders.sclpll
  functions/normalize.py
  plugins/
  contracts/orders.json
  fixtures/orders.json
  tests/orders.test.toml
  tests/snapshots/
  outputs/
  .sclpl/                 # ignored local state, artifacts, environment selection
  .gitignore
```

The manifest schema covers metadata, workflow/function/plugin paths, environments,
auth profiles, cache policy, output defaults, secret namespaces, runtime limits,
contract/test discovery, package inclusion, registries, notifications, and policy.
Unknown keys and unsupported schema versions fail with source locations. Commit
logical secret references; keep environment selection and resolved credentials local.

### 3.2 Identity, locking, and reproducibility

Define a single versioned identity document, reused by locks, cache namespaces, run
records, checkpoints, package manifests, and changed-test selection:

- Canonical compiled workflow digest plus exact source digest.
- Referenced function/plugin source or installed artifact hashes, plugin API/version,
  declared capabilities, and transitive dependency metadata.
- Effective nonsecret execution configuration, declared environment overlays, policy,
  contract/test schema versions, and input/fixture digests where applicable.
- Runtime version, Python/platform compatibility information, and installed dependency
  inventory. Record an external dependency lock digest when one exists.
- Git commit and relevant dirty-file state when Git is available; no Git requirement
  for ordinary local runs.

The workflow lock verifies an environment; it is not a new general Python dependency
resolver. CI installs dependencies through an explicitly pinned environment and then
checks the workflow lock. Native wheels may need platform-specific entries. Detect
version changes and same-version code changes. Inspect distributions/manifests without
importing plugin modules. Exclude timestamps, absolute machine paths, output contents,
credentials, and volatile local state from portable lock digests.

`workflow lock` updates deliberately; `workflow lock --check` and `run --locked` never
rewrite. `--require-clean` rejects relevant changed or untracked dependency files even
if someone regenerated the lock locally. Track the dependency closure, not unrelated
repository changes. Record exact runtime inputs in each run identity without requiring
every ordinary CLI variable override to rewrite the project lock; strict policy can
restrict overrides. Distinguish lock compatibility from exact run equivalence.

Reproducibility means identified code/configuration and repeatable fixture-driven
execution. It does not promise identical live API data or byte-identical Excel/Parquet
across library versions. Define logical table equality and canonical row ordering where
required; preserve user-specified order otherwise.

### 3.3 Shared execution services

Use one request lifecycle: resolve request, apply policy/auth, select live or fixture
transport, apply live cache/retry/rate policy, collect attempt events, validate the
response, and expose typed results. Put fixture interception at the request-attempt
boundary so retry/failure tests can exercise recorded sequences. Replay bypasses live
credential acquisition, real backoff waits, and live cache through explicit test services.

One versioned request fingerprint includes method, normalized URL, ordered duplicate
query parameters, selected headers, and body identity. Fixture matching also includes
logical step/iteration/page and occurrence information so concurrency cannot consume
another request's response. Do not normalize away semantically meaningful ordering.
Separate fixture identity from authorization-sensitive live cache identity.

One artifact store supplies fixture bodies, output hashes, lineage references, and
resume checkpoints. It supports atomic writes, content verification, retention, and
bounded storage. Artifacts referenced by pinned/resumable runs are retention roots.
Do not reuse disposable spill files as durable checkpoints or persist unsafe pickle
payloads as portable package/checkpoint data.

One event stream supplies terminal progress, JSON reports, HTML, lineage, history, and
notification payloads. Capture run start immediately and step attempts as they occur;
do not reconstruct all measurements from a final success/failure list.

### 3.4 Secrets and trust boundaries

Resolve secrets only when needed and register them before sending a request. Omit auth
headers, cookies, token endpoint bodies, proxy credentials, and sensitive query/body
fields from persistent request representations. Store reconstructable safe arguments
and logical secret references instead of raw `sys.argv`.

Redaction must cover logs, errors, history, reports, fixtures, snapshots, exports,
checkpoint values, package content, notifications, and stdout. Fail a managed artifact
write when sensitive data cannot be safely sanitized without corrupting its meaning;
do not silently publish an unreadable binary artifact. Keep dedicated, explicit
`secret get` credential retrieval separate from workflow-output guarantees.

Test echoed credentials and supported encodings in responses, nested values, exception
messages, short values, and streamed chunk boundaries. Avoid naive global substitution
as the sole boundary. Document that arbitrary transformations and trusted Python code
cannot be fully controlled by string redaction. Strict execution can refuse local
Python/plugins and enforce managed HTTP/file boundaries; capability declarations are
admission checks, not an OS sandbox. Do not market them as containment of malicious code.

### 3.5 Validation-gated output publication

Add a managed publication phase: stage outputs, finish all required validation and
completeness checks, then publish. Reference dependencies alone are insufficient: an
assertion branch and an export branch may run independently. The default new-project
policy requires all selected required assertions/contracts to pass before publication;
explicit output-specific validation scopes must be checked for dependency closure.

Stage on the destination filesystem for atomic per-file replacement. Preserve the last
valid output when validation fails. Multiple independent file replacements are not a
transaction: publish an immutable output generation plus an atomically replaced manifest
pointer when consumers need all-or-nothing visibility across files. For legacy fixed
paths, document per-file atomicity and record interrupted multi-output publication.
SQLite output uses a short transaction after validation, with busy handling and rollback;
do not keep a write transaction open throughout network extraction. Cross-database or
file-plus-database atomicity is not promised.

Validated stdout output must spool under disk/size limits before emitting bytes; it
cannot retract streamed data. Preserve existing streaming CLI behavior for legacy runs
and expose an explicit immediate-output mode, labeled unvalidated until completion.
New project templates select validated publication. Any compatibility change to existing
output timing is documented in the migration ADR. Arbitrary plugin/Python file writes
and remote API writes remain explicit side effects, outside managed publication.

### 3.6 Coordination between independent processes

Use short project-mutation locks for lockfile/environment/package metadata and exclusive
destination ownership for managed outputs. Independent runs targeting different outputs
may proceed concurrently. Canonicalize resource paths, account for Windows case rules
and path aliases, acquire multiple locks in stable order, and use bounded waits with
owner/run diagnostics. Never delete another live process's lock to make progress.

Use OS-backed lock lifetimes and atomic replacement where supported. Document shared
filesystem guarantees; refuse strict shared-writer operation on filesystems that cannot
provide the required coordination. This does not create a distributed lock service.
Coordinate artifact reference updates with pruning transactionally. Stale metadata must
not imply ownership after process death, and PID reuse must not establish ownership.

### 3.7 Data fidelity and explicit completeness

Define a format capability matrix for decimal precision/scale, arbitrary-size identifiers,
timestamp timezone/offset, missing versus null, strings with leading zeros, Unicode,
nonfinite floats, and empty typed datasets. Casts must be explicit; lossy conversion
fails by default in validated publication unless the workflow declares its conversion
policy. CSV cannot carry an intrinsic type schema: use an explicit read schema or
versioned sidecar. Document Excel and JSON representation limits rather than claiming
universal lossless round trips. Include chosen conversion policy in run identity.

Record execution status separately from data completeness (`complete`, `partial`, or
`unknown`) and publication state (`staged`, `published`, `withheld`, or `interrupted`).
Completeness is relative to the declared extraction scope, not proof that a remote API
returned every real-world record. Reaching `max_pages` with a continuation token,
failed required branches, and truncated streams cannot silently count as complete.
Intentional workflow modes define a smaller expected scope and are not inherently partial.

Record missing branches/pages or unknown counts with reasons. Keep existing failure,
assertion, and cancellation exit codes. `run --require-complete` fails validation when
completeness is partial/unknown without another failure code; new validated project
templates enable this policy. Explicit partial-output opt-in labels artifacts/reports
and does not turn a failed run into success. Carry these states through cache entries,
checkpoints, lineage, reports, notifications, and resume; partial cache data must never
satisfy a complete-data requirement without revalidation.

## 4. Command contract and compatibility

All commands below are target syntax, not claims about current availability. Retain
existing stdout/stderr behavior, JSON automation surfaces, bare workflow shorthand,
secret backends, retention defaults, and standalone-file execution.

| Area | Target commands and behavior |
|---|---|
| Project | `sclpl init [PATH]`, `project check [--json]`, `workflow list` |
| Environments | `env create NAME`, `env list`, `env show NAME`, `env use NAME`; consistent `--env` on execution/testing commands |
| Locks | `workflow lock [NAME] [--check]`, `run NAME --locked [--require-clean]` |
| Tests | `test [PATH] [--changed --base REF] [--update-snapshots]`; `workflow test` delegates to the same implementation |
| Contracts | `contract generate WORKFLOW`, `contract check WORKFLOW`; fixture input by default, live execution explicit |
| Fixtures | `call ... --record PATH`, `call ... --replay PATH`, `run NAME --record PATH`, `workflow replay NAME --fixture PATH` |
| Reports | `runs report latest`, `runs diff latest previous`, `runs export latest --format html --into report.html` |
| Lineage/resume | `runs lineage ID`, `explain --lineage PATH`, `runs resume ID [--dry-run]` |
| Packages | `package build`, `package validate PATH`, `package install SOURCE`, `package list`, `package remove NAME` |
| Registry | `registry add NAME URL`, `registry list`, `package install vendor/orders@VERSION --registry NAME` |
| Import | `import curl request.txt`, `import openapi spec.json`, `import postman collection.json`; existing `import FILE --scope ...` retained |
| Analysis | `lint [PATH] [--json]`, `graph WORKFLOW --format mermaid`, `audit [PATH] [--json]` |
| Notifications | Manifest-driven completion/failure hooks; `notify test PROFILE` only when explicitly invoked |
| Output trust | `run NAME --require-complete`; manifest publication policy `validated` or explicit `immediate`, with separate opt-in for partial artifacts |

For `import`, use a narrowly defined entrypoint compatibility dispatcher: recognized
format plus a source becomes an adapter operation; legacy file syntax retains catalogue
behavior. Provide `import --format curl PATH` and `import -- PATH` to disambiguate files
named after formats. Test grouped commands and bare shorthand routing together.

Keep `runs replay ID` printing a safe rerun command. It must not start performing
network operations after this upgrade. Existing JSON `runs export --into` remains the
default; HTML is explicit. Resolve `latest` and `previous` deterministically with
workflow/environment filters and a stable tie-breaker.

Preserve exits 0 success, 1 execution failure, 2 usage, 3 validation, 4 assertion,
5 cache miss, 6 unknown target, 130 interruption. Add machine-readable diagnostic
identifiers for lock drift, policy refusal, fixture mismatch, auth failure, and unsafe
resume while mapping to compatible exit categories. Define new numeric codes only
through the compatibility ADR, if actually needed.

## 5. Dependency-ordered implementation batches

Each numbered subtask is a focused slice, normally two production files plus a focused
test module and documentation. File names marked new are proposed ownership, not a
requirement to create abstractions prematurely. If a slice exceeds about five files,
split its plumbing and CLI integration while retaining the same acceptance check.
Every batch must leave existing workflows runnable. Checkpoints are verification gates,
not repeated permission requests or public releases.

### Batch A — Baseline, version contracts, and policy-safe startup

Dependencies: none. Main areas: `docs/adr/`, `docs/cli-rebuild/SPEC.md`,
`sclpl/cli/app.py`, `bootstrap.py`, `ext/plugins.py`, `scripts/`.

1. **A1 — Capture compatibility baseline.** Record existing command help, exits, JSON
   shapes, sample workflow outputs, state schema, plugin ABI, and benchmark inputs.
   Accept: a documented baseline and regression fixtures cover existing public behavior.
   Verify with current CLI integration tests and representative standalone workflows.
2. **A2 — Define version and migration contracts.** Add the upgrade ADR, artifact schema
   policy, stable/experimental table, compatibility window, and budget revision.
   Accept: every persistent format has a version and unknown-new-version behavior;
   all new packages are budgeted. Verify budget and schema-document consistency.
3. **A3 — Split plugin discovery and activation.** Read metadata before executing code;
   pass an explicit approved inventory to activation. Keep help and static inspection
   usable without importing project code. Accept: a denied plugin's import sentinel
   never executes. Verify installed, bundled, local, invalid-manifest, and ABI cases.
4. **A4 — Strengthen architectural gates.** Detect longer dependency cycles and uncounted
   packages. Accept: synthetic three-node cycles and unknown package fixtures fail.
   Verify checker tests and run both checks against the baseline.
5. **A5 — Close existing credential persistence gaps first.** Add sentinel regression
   tests around current argv/history, errors, logs, stdout, and file sinks; replace raw
   argument persistence with safe structured arguments and logical secret references.
   Accept: known credentials never persist through managed paths, and `secret get`
   remains an explicit separate retrieval operation. Verify query/header/variable
   secrets, echoed responses, nested exception values, and current secret backends.
   Establish reusable leak-test helpers here and extend them with every later sink.

Checkpoint A: baseline suite green, old CLI contracts preserved, startup admission
boundary and existing credential sinks tested, schema ownership and budget decisions
documented. A5 must pass before new persistence surfaces are added.

### Batch B — Projects, environments, and authentication

Dependencies: A. Areas: new `sclpl/project/`, `cli/project_cmd.py`, `cli/env_cmd.py`,
`cli/options.py`, `catalog/resolve.py`, `state/secrets.py`, `run/runner.py`.

1. **B1 — Manifest loading and resolution.** Implement schema validation, root discovery,
   path resolution, and precedence. Accept: nested invocation resolves identically;
   invalid keys identify their source; standalone execution works. Verify table-driven
   precedence, Windows paths, ambiguous names, and nonexistent roots.
2. **B2 — Project initialization.** Generate the conventional layout, safe ignores, and
   a small fixture-backed reporting example. Accept: `init`, `project check`, and
   `workflow list` work immediately; rerunning does not overwrite user files. Verify
   empty and existing directories plus paths containing spaces.
3. **B3 — Named environments.** Add selection, overlays, logical namespaces, and effective
   context reporting. Accept: switching staging changes endpoint and secret namespace,
   creates no committed credential, and affects all execution entrypoints consistently.
   Verify explicit override precedence and missing-secret failures.
4. **B4 — Basic auth profiles.** Support API-key header/query, bearer, basic, and custom
   headers through one provider interface. Accept: auth is applied once and omitted from
   safe context/history. Verify duplicate/conflicting auth and cross-origin redirects.
5. **B5 — OAuth2 client credentials.** Add token acquisition, expiry/skew handling,
   concurrent refresh coordination, and bounded refresh after authentication rejection.
   Accept: concurrent requests share valid tokens, token bodies never persist, repeated
   rejection stops. Verify with a local token server and injected clock.
6. **B6 — HMAC signing.** Define a documented canonical request signer and extension hook
   for provider-specific schemes. Accept: byte-exact vectors match, retries receive the
   required fresh timestamp/signature, and secrets are absent from diagnostics. Verify
   body/query canonicalization and clock-offset errors without promising every vendor.

Checkpoint B: initialized project runs against a local API with both environments;
all auth modes are exercised, and plugin admission uses the resolved context.

### Batch C — Execution identity, locks, and migration infrastructure

Dependencies: B. Areas: new `project/lock.py`, `project/identity.py`,
`state/migrations.py`, `state/db.py`, `values/digest.py`, `run/preflight.py`.

1. **C1 — Canonical dependency identity.** Hash workflow/function/plugin/configuration
   closure using deterministic serialization. Accept: portable equivalent projects
   agree; changed code or effective settings differ; secrets are excluded. Verify
   formatting versus semantic changes, local modules, and platform metadata.
2. **C2 — Lock generation and checking.** Add per-workflow lock entries, project-wide
   checking, runtime compatibility, and clean-tree enforcement. Accept: same-version
   plugin mutation fails before import; check never writes; missing dependencies give
   remedies. Verify clean/dirty/untracked Git fixtures and non-Git operation.
3. **C3 — State migrations.** Introduce transactional, versioned SQLite migrations,
   pre-migration backup, schema refusal, and migration recovery. Accept: existing runs,
   pins, tags, ports, and logs remain readable. Verify an old database, interrupted
   migration, repeated startup, newer schema, and backup restoration.
4. **C4 — Provenance at run start.** Persist identity and safe arguments before scheduling;
   define required persistence for resumable/audited runs and best-effort history for
   ordinary runs. Accept: a killed run has identifiable state; storage failure is
   visible and follows the selected policy. Verify readonly/full storage fault paths.
5. **C5 — Coordinate project mutations and destination ownership.** Add shared locking
   primitives in proposed `state/locking.py`; use them for manifest/lock updates and
   acquire output ownership before execution side effects. Accept: competing writes
   wait within a bound or fail with owner details, while nonconflicting runs proceed.
   Verify separate OS processes, crash/restart, lock ordering, path aliases, and Windows
   case variants. Integrate these same primitives into package install, publication,
   environment selection, and artifact pruning as those slices land.

Checkpoint C: a locked project verifies before activation, historical databases upgrade,
and each new run identifies its actual source/configuration.
Competing project/output writers must have verified admission behavior before Batch D.

### Batch D — Complete HTTP behavior and fixture replay

Dependencies: C. Areas: `run/transport.py`, `retry.py`, `execute.py`, `values/cache.py`,
new `run/fixtures.py`, `state/artifacts.py`, HTTP CLI and IR/parser adapters.

1. **D1 — Transport service injection.** Route call/workflow HTTP through one request
   interface with injectable transport, clock, randomness, and attempt events.
   Accept: existing retry/pagination behavior remains compatible. Verify current
   transport, call, pagination, and scheduling tests before adding modes.
2. **D2 — Host/proxy policy completion.** Wire host ceilings, Retry-After date/delta,
   capped backoff, breaker recovery, proxy/TLS profiles, and explicit proxy-environment
   behavior. Accept: no cross-profile credential leakage; unsafe methods require an
   explicit retry/idempotency policy. Verify local proxy, 429/503, cancellation, and
   concurrent breaker transitions with virtual time.
3. **D3 — Conditional HTTP caching.** Implement ETag and Last-Modified revalidation,
   304 body reuse, changed 200 replacement, expiry, Vary, and no-store rules.
   Accept: cached bodies never cross auth/environment identities; a 304 without a body
   has a defined recovery path. Verify authenticated partitions, credential rotation,
   stale entries, and distinguish HTTP revalidation from step-result caching.
4. **D4 — Multipart and streaming.** Add bounded-memory uploads/downloads, incremental
   checksums, temporary-file cleanup, cancellation, and atomic final publication.
   Accept: checksum mismatch never replaces a valid output; request handles close;
   non-rewindable uploads cannot be silently retried. Verify large local streams,
   partial responses, path constraints, and disk failures.
5. **D5 — Artifact-backed recording.** Define versioned request/response fixtures,
   occurrence identifiers, separate binary blobs, configurable size limits, and sensitive
   field sanitation. Accept: paginated and repeated calls record without secrets and
   verify their body digests. Verify parallel identical requests and redacted bodies.
6. **D6 — Strict replay.** Inject fixture responses and recorded attempt failures;
   reject missing, ambiguous, and unexpectedly unused fixtures. Accept: replay opens
   no live HTTP connection, never refreshes OAuth, and preserves retry/pagination paths.
   Verify under network-denying tests; refuse network-capable extension execution in
   strict replay because arbitrary Python cannot be transport-intercepted safely.
7. **D7 — Extraction completeness signals.** Extend pagination/transport result metadata
   with declared scope, termination reason, received counts, continuation state, and
   known omissions. Accept: a page ceiling with more data is partial; unknown remote
   totals remain unknown; intentional bounded extraction can be complete for its
   declared scope. Verify mid-pagination exhaustion, repeated cursors, truncated
   responses, source exhaustion, replay, and cache round trips.

Checkpoint D: record a paginated flaky endpoint, stop its server, replay the workflow,
and compare the typed output. Check conditional revalidation and large-file behavior
separately against local servers.

### Batch E — Contracts, workflow tests, and static analysis

Dependencies: D. Areas: new `sclpl/contracts/`, `sclpl/testing/`, `sclpl/analysis/`,
`functions/diagnostics.py`, `run/preflight.py`, `cli/` thin adapters.

1. **E1 — Shared assertion evaluator.** Cover status, field presence, nullability, type,
   inclusive/exclusive numeric bounds, enum, and row/cardinality rules. Accept: inline
   assertions and external contracts produce consistent failures with step/data paths.
   Verify empty arrays, missing versus null, booleans versus integers, nested records.
2. **E2 — Schema contracts and generation.** Support an explicitly documented JSON Schema
   dialect and local reference resolution; disable remote schema fetching by default.
   Generate a candidate from selected fixture samples. Accept: generation never silently
   replaces an accepted baseline; check flags breaking shape/type changes. Verify
   optional/additive fields, references, heterogeneous arrays, and insufficient samples.
3. **E3 — Project test discovery.** Define test manifests with workflow, environment,
   inputs, fixture, expected exit, assertions, and expected outputs. Accept: each test
   uses isolated state/temp outputs and offline execution by default. Verify validation,
   pagination, branches, failure recovery, and contract-failure exit 4.
4. **E4 — Snapshots and changed selection.** Compare structured tables logically and
   text deterministically; normalize volatile fields only by explicit rules. Accept:
   updates are opt-in and atomic; shared plugin/config changes select all dependent
   tests; unavailable Git base conservatively runs all. Verify deleted files, renames,
   untracked files, and Windows/Linux snapshot consistency.
5. **E5 — Lint and graph.** Reuse compiled references/source spans for unused variables,
   unreachable branches where provable, unbounded loops, and missing retry/timeout
   policy. Accept: effective defaults suppress false missing-policy warnings and dynamic
   uncertainty is reported honestly. Verify fixtures for each rule and stable graph output.
6. **E6 — Audit and enforced policy.** Inspect capabilities, secret interpolation, host
   allowlists, output roots, and overwrite controls; enforce managed boundaries at
   runtime. Accept: policy denial precedes side effects and plugin import; unknown
   dynamic behavior cannot be declared safe. Verify path traversal, symlinks/junctions,
   redirect escapes, and attempted policy relaxation.
7. **E7 — Publication eligibility.** Derive each managed output's required validation
   scope and completeness rule from the selected workflow. Accept: an assertion branch
   cannot be bypassed by a faster independent export; missing validation dependencies
   fail preflight. Verify conditional/mode selection, keep-going failures, cache-supplied
   data, optional branches, and explicit partial-output policy.
8. **E8 — Stage and publish managed outputs.** Add proposed `run/publication.py`, integrate
   `tables/io.py`, then wire validated publication into the runner as a separate slice.
   Accept: no destination changes before E7 passes; per-file replacement is atomic;
   SQLite failure rolls back; generation-manifest publication exposes complete output
   sets. Verify late assertion failure, disk full, process death during publication,
   stdout spooling limits, cross-filesystem rejection, and lock contention using C5.
9. **E9 — Verify format fidelity.** Add the documented conversion matrix and explicit
   serializer/read-schema policies, then round-trip tests for each supported format.
   Accept: decimals, timezone-aware timestamps, large IDs, `00123`, nulls, and empty
   tables retain declared meaning or fail with a loss diagnostic. Verify JSON, NDJSON,
   CSV, Excel, Parquet, and SQLite, including exports produced after spill/checkpoint
   serialization. Reuse existing uniqueness/null/deduplication functions.

Checkpoint E: all five business workflows below have passing replay tests, contracts,
and meaningful negative cases. Static tools do not execute project Python to inspect it.
Publication withholding, separate-process contention, and format-fidelity cases must pass.

### Batch F — Run events, reports, and lineage

Dependencies: C and E. Areas: `render/events.py`, `render/reporter.py`,
`run/runner.py`, `state/db.py`, new `state/lineage.py`, report renderers and CLI.

1. **F1 — Complete event measurements.** Persist request/attempt totals, timings, bytes,
   cache outcomes, per-step status, output rows/digests, warnings, and environment.
   Accept: report counts reconcile with observed local-server requests; start/end
   timestamps reflect real lifecycle. Verify retries, cached steps, skipped paths,
   failures, cancellation, and concurrent execution.
2. **F2 — Reports and comparisons.** Add human/JSON summaries and self-contained escaped
   HTML; compare compatible runs by workflow/environment/identity. Accept: old runs
   show unknown measurements rather than fabricated zeros; reports need no external
   scripts/assets. Verify malicious response strings, empty history, and selector ties.
3. **F3 — Output lineage.** Record runtime edges from inputs and request descriptors
   through executed transforms to output artifacts, including expanded iterations.
   Accept: output-path lookup resolves the producing run/digest and reports ambiguity
   or later modification. Verify joins, fan-out, skipped branches, reused artifacts,
   and pruned parents. This release provides step/artifact lineage, not cell lineage.
4. **F4 — Retention consistency.** Make history pruning respect pins, checkpoint roots,
   notification references, and shared blobs; clean unreferenced artifacts safely.
   Accept: pruning one run cannot break another retained run. Verify shared digests,
   crash leftovers, storage quotas, and concurrent readers.
5. **F5 — Partial-result reporting and automation.** Persist and expose execution,
   completeness, and publication states independently, including missing-page/branch
   reasons. Accept: human/JSON/HTML/JUnit output cannot label partial data as complete;
   `--require-complete` follows section 3.7 exit rules. Verify cancelled and keep-going
   runs, withheld outputs, explicit partial publication, old runs with unknown coverage,
   and consistent notification/lineage payloads when those consumers are integrated.

Checkpoint F: a single run's terminal summary, JSON, HTML, lineage, and persisted
measurements agree; all share the same sanitized source data.

### Batch G — Safe failed-run resume

Dependencies: F. Areas: new `run/checkpoints.py`, `state/artifacts.py`,
`run/runner.py`, `schedule.py`, `state/db.py`, resume CLI.

1. **G1 — Durable checkpoints.** Store eligible completed step values using versioned
   JSON/Arrow/file artifacts and transactional status updates. Accept: a checkpoint
   is reusable only after its blobs and metadata are durably committed. Verify process
   termination before/after each persistence boundary and unsupported value types.
2. **G2 — Resume eligibility planning.** Compare workflow/dependency/config/input identity,
   artifact integrity, execution mode, and side-effect classification. Accept: dry-run
   explains reuse/rerun/refusal for every step; drift and missing artifacts invalidate
   affected steps and descendants. Verify changed upstream inputs and dynamic graphs.
3. **G3 — Resume execution.** Rehydrate eligible values and execute the remaining graph
   under a new run linked to its parent. Accept: a successful durable export is not
   duplicated; an uncertain non-idempotent HTTP write is refused without an explicit
   safe recovery policy. Verify interruption during writes, expired auth, foreach
   iteration identities, and lock mismatch. No exactly-once promise for external APIs.
4. **G4 — Recover publication without duplicating it.** Persist publication intent,
   generation identifiers, and completion receipts; validate destination digests during
   resume under C5 locks. Accept: staged/unvalidated outputs are never reused as trusted
   published artifacts, completed generations are recognized, and ambiguous fixed-path
   multi-output commits are reported for safe recovery. Verify interruption before and
   after each file/manifest/SQLite commit and propagation of incomplete upstream data.

Checkpoint G: interrupt a multi-step integration, resume safely, and compare final
logical outputs with a clean run; demonstrate refusal of ambiguous side effects.

### Batch H — Packages, plugin lifecycle, and shared registry

Dependencies: E and F; G supplies resume-aware retention behavior. Areas: new
`sclpl/packages/`, `catalog/store.py`, `ext/plugins.py`, `cli/plugin_cmd.py`.

1. **H1 — Package manifest/build.** Bundle declared workflows, functions, plugins,
   schemas, fixtures, docs, capabilities, and version/lock metadata. Accept: repeated
   builds produce identical bytes after archive metadata normalization; secrets,
   outputs, caches, and local state are excluded. Verify allowlists and hidden files.
2. **H2 — Validation/install.** Check schema, hashes, compatibility, capability policy,
   archive limits, and paths before atomic installation into project-managed storage.
   Accept: validation/import never executes package code; failed installs leave the
   prior version usable. Verify traversal, links, archive bombs, tampering, and collisions.
3. **H3 — Plugin lifecycle.** Add inspect/verify/update/remove behavior around the locked
   inventory, with an explicit update diff and dependency-aware removal. Accept: no
   silent plugin upgrade during run; referenced versions cannot disappear without a
   clear refusal or explicit project change. Verify ABI and same-version hash drift.
4. **H4 — Shared distribution.** Support a versioned static index over local/shared
   directories or HTTPS with immutable versioned artifacts and secret-backed auth.
   Accept: two clean workspaces install the same pinned package digest; missing or
   altered releases fail. Verify cache/offline installation and credential isolation.
   This is a registry client and documented hosting layout, not a new registry server.
5. **H5 — Registry release workflow.** Build index/artifact outputs for publishing via
   existing team CI/storage tools. Accept: duplicate name/version with different bytes
   is rejected and origin/authenticity assumptions are explicit. Hashes verify integrity;
   trusted HTTPS/index provenance is still required. Registry publication is an explicit
   operation, never a side effect of `package build` or `install`.

Checkpoint H: package a tested reporting project, install from a team registry in an
isolated workspace, verify its lock, and replay its tests without the author's machine.

### Batch I — Import adapters, notifications, and CI integrations

Dependencies: H. Areas: new `sclpl/importers/`, notification plugin modules,
`cli/catalog_cmd.py`, `cli/app.py`, `state/db.py`, project templates.

1. **I1 — cURL import.** Parse supported methods, URLs, headers, query, JSON/form bodies,
   auth references, and file uploads as data, never by executing a shell command.
   Accept: generated workflows pass normal preflight and reproduce supported local
   requests; unsupported shell features receive actionable diagnostics. Verify POSIX,
   PowerShell, Windows quoting, repeated parameters, and credential extraction.
2. **I2 — OpenAPI import.** Document supported 3.x versions, select operations, resolve
   local references, and map parameters/body/auth/schema to workflow templates/contracts.
   Accept: required missing values become explicit inputs; unsupported constructs fail
   or produce clearly marked diagnostics. Verify local specs and disable implicit remote
   reference fetches. Imported schemas remain distinct from sampled schema snapshots.
3. **I3 — Postman import.** Support a documented collection version, folders, requests,
   variables, and common auth. Accept: compatible requests run; pre-request/test scripts
   are reported as unsupported and never executed or silently discarded. Verify
   environment separation and redacted generated files.
4. **I4 — Notification hooks.** Add terminal-run event hooks and webhook, Slack webhook,
   and SMTP/email plugins with bounded retries and delivery receipts. Accept: payloads
   contain sanitized summaries, opt-in configuration controls sending, and notification
   failure does not rewrite the workflow result. Verify local fake receivers, timeouts,
   duplicate event handling, and idempotency keys. Delivery is best effort with recorded
   status; durable post-process delivery needs the deferred operations layer.
5. **I5 — CI output and templates.** Emit JUnit and stable JSON test results, diagnostics,
   lock checks, policy checks, HTML run artifacts, and an offline project CI template.
   Accept: the template detects fixture/contract drift with meaningful exit codes and
   contains no credentials or live default calls. Verify it against generated projects.

Checkpoint I: import a request, turn it into a tested package, install it elsewhere,
execute in CI, and observe a test notification through local fake receivers.

### Batch J — Integrated validation, migration guide, and release

Dependencies: all preceding batches. Areas: tests, examples, documentation, CI,
`pyproject.toml`, `sclpl/__init__.py`, release/build metadata.

1. **J1 — Business acceptance examples.** Deliver the five journeys below with fixture
   data, expected outputs, contracts, and concise operational documentation. Accept:
   each runs offline after a clean install and demonstrates a useful failure case.
2. **J2 — Cross-platform and security matrix.** Run supported Python endpoints on Linux,
   Windows, and macOS; add dependency-extra and secret-backend jobs. Accept: all managed
   output surfaces pass sentinel tests and supported platforms pass path/install/resume
   cases. Unix PTY tests remain platform-appropriate with explicit Windows alternatives.
3. **J3 — Performance and fault validation.** Compare baseline workloads with regression
   thresholds below; exercise cancellation, crashes, missing artifacts, and disk errors.
   Accept: bounded behavior and documented limits, not only happy-path correctness.
   Include two-process destination races, late-validation publication withholding,
   all-format fidelity fixtures, and partial-result policy in the release matrix.
4. **J4 — Documentation and migration.** Update SPEC through ADRs, stability policy,
   limitations, vault, playbooks, generated reference, and install instructions.
   Accept: current workflows still run; old history upgrades; new formats reject older
   incompatible readers clearly. Verify examples execute as well as parse.
5. **J5 — Release artifact verification.** Set final package version once, build wheel
   and sdist, install each in a clean environment, and rerun representative commands.
   Accept: packaged templates/schemas/plugins are present and entrypoints work away
   from the checkout. Finalize one squash commit only after the integrated gates pass.

## 6. What is deliberately shared across the original releases

| Shared implementation | Features completed together | Avoided duplication |
|---|---|---|
| Project context | init, environments, output defaults, tests, policy, package roots | Separate config loaders for each command |
| Execution identity | locks, Git checks, cache partitions, lineage, resume, package verification | Incompatible hashing and drift rules |
| Metadata-only plugin discovery | lock checking, audit, lifecycle, package validation | Importing code to discover whether it is allowed |
| Transport interception | auth, recording, replay, contract samples, HTTP metrics | A mock HTTP stack unrelated to real execution |
| Assertion evaluator | inline validation, contracts, tests, schema drift | Multiple incompatible definitions of failure |
| Artifact store | fixture blobs, outputs, checkpoints, retained package data | Separate unsafe persistence and pruning implementations |
| Event model and run store | reports, diffs, lineage, resume status, notifications | Late reconstruction or parallel measurement systems |
| Compiled workflow graph | runner, lint, graph, changed-test selection, lineage planning | Multiple parsers or dependency walkers |
| Import-to-IR path | cURL, OpenAPI, Postman | Independent workflow generators with different semantics |
| Migration/release framework | all persistent features and CLI additions | Three separate upgrade and documentation cycles |

Do not combine API-result caching, HTTP revalidation, fixture replay, and resume into
one behavioral mode. They share identity/artifact primitives but answer different
questions and must retain explicit semantics.

## 7. End-to-end business acceptance

| Journey | Passing result | Required negative case |
|---|---|---|
| API-to-CSV/Excel reporting | Init, paginate, contract-check, normalize, export, report rows and origin | Required field disappears; no trusted final report is published |
| API reconciliation | API plus local CSV/SQLite produces a stable discrepancy report with lineage | Duplicate/missing join keys trigger explicit validation |
| API quality monitoring | Fixture/live contract comparison produces a machine-readable failure and notification event | Breaking schema change fails CI; delivery failure is separately recorded |
| Lightweight ingestion | Typed records stream/spill into Parquet/SQLite within configured limits | Interrupted output is not mistaken for a completed dataset |
| Integration regression testing | Installed package replays pagination, errors, auth references, and output snapshots offline | Missing fixture, lock drift, or unsafe plugin capability fails before side effects |

Use local synthetic APIs and sanitized fixtures, not provider accounts, for release
acceptance. Live vendor examples are optional operational checks, never default tests.

## 8. Verification strategy and release gates

Run focused tests for each changed slice. Run the complete fast suite at batch
checkpoints, and the expensive OS/install/performance matrix at integration gates and
on release candidates. Repeat a gate when relevant code changes or a failure leaves
uncertainty; avoid rebuilding the same unchanged candidate repeatedly.

Existing repository checks to retain and explicitly wire into CI:

```text
python -m ruff check sclpl tests scripts
python -m ruff format --check sclpl tests scripts
python -m mypy
python -m pytest -q
python scripts/check_budget.py
python scripts/check_layering.py
python scripts/check_vault.py
sclpl docs build --check
```

Add generated-project smoke tests, example execution, lock/contract/replay tests,
old-state migrations, wheel/sdist install checks, JUnit validation, and package
tamper tests. Add an explicit build frontend to release tooling before relying on
`python -m build`; it is not currently a declared development dependency.

Suggested initial performance acceptance budgets, calibrated and recorded in A1:

- 1,000-step synthetic workflow: no more than 15% median overhead versus baseline on
  the same machine for unchanged behavior, measured over at least five runs.
- 100,000-row paginated reporting fixture: no more than 20% throughput regression for
  unchanged transformations with new optional features disabled.
- Large streaming download: memory does not grow with total payload size; measure peak
  RSS against the configured budget plus a documented interpreter/library allowance.
- 10,000 retained run records: latest/report metadata queries target under one second
  on the benchmark machine; test retention without deleting shared live artifacts.
- Replay performs zero live network attempts; instrument attempts rather than relying
  on an unavailable server. Bound fixture, artifact, and retry resource usage.

These are proposed engineering gates, not measured performance claims. Store workload,
hardware, library versions, and results; investigate regressions before changing budgets.

Release requires all advertised commands implemented, no default-network tests,
compatibility checks green, migration recovery exercised, no known credential leakage
in managed surfaces, and no unresolved correctness failures in resume or package install.
Experimental features must be explicitly marked and cannot stand in for required
acceptance criteria. Unsupported behavior must fail clearly rather than act as a stub.

## 9. Migration, rollback, and stability

1. Preserve source files and existing catalogue resolution unless a project explicitly
   opts into the new layout. Do not auto-rewrite old workflows on run.
2. Keep workflow-schema compatibility separate from workflow revision numbers. Add an
   explicit migration command only for transformations actually required by the new schema;
   provide check/diff behavior before writing.
3. Back up existing SQLite state before the first structural migration. Recover failed
   migrations transactionally; older binaries must refuse unsupported newer databases.
4. Release rollback uses the previous executable plus its pre-upgrade database backup
   in a separate state directory. It does not reverse remote API writes or restore
   overwritten business outputs automatically. Package installation keeps the previous
   version until successful activation.
5. Stable additions preserve their CLI/JSON/format contracts throughout the 2.x series;
   publish deprecations and replacements before a future major removal. Label plugin
   ABI, auth signer, fixture, package, and checkpoint compatibility independently.
6. Retain existing deliberate limitations unless explicitly covered here. In particular,
   nested `use` workflow execution, Arrow process-lane transport, adaptive lane learning,
   and large fan-out terminal presentation are separate runner improvements.

## 10. Commit/build execution model

Use one integration branch for this upgrade. Keep the task IDs and verification
evidence in a progress checklist beside this plan. Implement A through J in dependency
order; temporary local commits are useful recovery points but are not separate releases.
Squash to one final reviewable commit after all gates. No committing or publishing is
performed as part of writing this plan.

Suggested final commit subject:

```text
feat: deliver unified sclpl 2.1 workflow reliability and team CLI upgrade
```

The final commit contains implementation, focused regression tests, migrations,
business examples, generated documentation, CI, and the version bump together.
Do not build three distributions or maintain three incompatible migration branches.
Build one final candidate and verify those exact artifacts; code changes invalidate
the candidate and require an appropriate rebuild.

The efficiency gain is shared engineering and one release cycle. It does not make
this scope a small change or justify skipping negative tests. Keep changes recoverable
through checkpoints even though the final Git history presents one clean commit.

## 11. Primary risks and concrete mitigations

| Risk | Consequence | Mitigation / owning batch |
|---|---|---|
| Plugin import before admission | Lock/policy checks happen after arbitrary code runs | Metadata-first activation, sentinel tests; A/B/C |
| False reproducibility promise | Locked live API runs still change | Separate code identity, live inputs, and fixture determinism; C/D |
| Fixture normalization collisions | Concurrent requests receive wrong responses | Preserve semantic ordering and logical occurrence identities; D |
| Auth/cache cross-contamination | One environment receives another account's data | Authorization-sensitive private cache partitions and rotation invalidation; B/D |
| Redaction only in reporter | Credentials persist through history/artifacts | Safe serializers and sink-wide sentinel tests; B through J |
| Resume repeats side effects | Duplicate writes or payments | Step eligibility, durable boundaries, idempotency policy, refusal; G |
| Capability checks mistaken for sandbox | Unsafe Python admitted under false assurances | Explicit trusted-code boundary and strict refusal mode; A/E |
| Package parser/extraction attacks | Writes escape project or resources exhaust | Validate paths, links, sizes, hashes before atomic installation; H |
| Broad import claims | Silent loss of source semantics | Published format subsets and explicit unsupported diagnostics; I |
| One huge unverified change | Expensive integration and rollback | Testable batches, progress evidence, final squash only after gates; all |
| Budget evasion and dependency cycles | Architecture becomes unmaintainable | Explicit package accounting and full cycle checks; A/J |

## 12. Product evidence after the upgrade

Use local run/report data and voluntary pilot feedback; add no default telemetry service.
Pilot the reporting and reconciliation examples with small teams, then collect:
time to first successful workflow, recurring workflows over 30 days, repeat-run use,
test/contract adoption, recovery success, package reuse, and user-reported manual hours
replaced. These validate the product thesis without requiring hosted infrastructure.

Separate engineering success from product success: passing release gates shows the
runner works; recurring workflows and retained users show that the upgrade is useful.
Pricing and paid-service implementation are outside this engineering commit.

## 13. Completion checklist

- [ ] A: compatibility baseline, version decisions, plugin startup, architecture gates.
- [ ] B: init, manifests, environments, secret namespaces, every scoped auth mode.
- [ ] C: identity, lock verification, Git checks, state migration, provenance.
- [ ] D: HTTP policies, revalidation, uploads/downloads, recording, strict replay.
- [ ] E: all assertion families, schemas, tests, snapshots, changed selection, analysis.
- [ ] F: measured reports, HTML/JSON, comparisons, lineage, consistent retention.
- [ ] G: durable checkpoints, safe resume planning/execution and refusal cases.
- [ ] H: reproducible packages, validated install, lifecycle, shared registry client.
- [ ] I: cURL/OpenAPI/Postman import, notifications, CI results and templates.
- [ ] J: five business journeys, platform matrix, security/performance, migration docs,
  clean artifact installation, and one final integrated release commit.
- [ ] Cross-cutting trust gates: A5 credential persistence, C5 process coordination,
  D7/F5 completeness, E7/E8 validated publication, E9 fidelity, and G4 recovery.

## 14. Comparison with alternatives

See [the feature-gap assessment](FEATURE-GAP-ASSESSMENT.md) for a sourced comparison
with Postman, Bruno, dlt, and Schemathesis. It distinguishes absent capabilities from
partially covered ergonomics and excludes this plan's deliberate deferrals. Candidate
features in that assessment are not automatically release commitments. The five
requirements in sections 3.5–3.7 and tasks A5/C5/D7/E7–E9/F5/G4 are incorporated scope.
