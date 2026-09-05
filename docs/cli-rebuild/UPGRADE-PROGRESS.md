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
- [ ] D3-D4 and D7 remain in the dependency order defined by the plan.
- [x] E3 foundation: schema-versioned, project-contained test manifests execute through
  the regular runner with fixture replay offline, isolated scratch state, expected-exit,
  local contract assertions, and JSON expected-output checks.
- [x] E5 foundation: `graph WORKFLOW --format mermaid` renders a deterministic validated DAG.
- [ ] E4 and E6-E9 remain in the dependency order defined by the plan.
