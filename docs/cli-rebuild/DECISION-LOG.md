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
