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
- [ ] A1 compatibility baseline and regression fixtures.
- [x] A3 metadata-first plugin activation: static discovery and CLI help avoid plugin
  import; approved inventory activation follows capability-policy validation.
- [ ] A5 credential-sink audit and regression helpers.

## Batch B

- [x] B1 strict manifest discovery and environment precedence.
- [x] B2 project initialization, `project check`, and `workflow list`.
- [x] B3 local environment selection and safe context reporting.
- [ ] B4-B6 authentication providers.

## Later batches

- [x] C1 canonical workflow identity from source and effective non-secret settings.
- [x] C2 explicit `workflow lock` generation, side-effect-free `--check` verification,
  and `run --locked` admission.
- [x] C3 versioned SQLite migration with pre-migration backups and newer-schema refusal.
- [x] C4 run provenance: a running record is persisted before scheduling; audited runs
  can require that storage admission through `--require-provenance`.
- [ ] C5 process coordination: workflow-lock mutation admission is protected; output
  ownership and remaining project mutations are still required.
- [x] D5-D6 foundation: versioned, redacted request/response fixtures support offline
  replay, recording, occurrence tracking, digest verification, and opt-in unused-fixture refusal.
- [ ] D1-D4 and D7 remain in the dependency order defined by the plan.
- [x] E3 foundation: schema-versioned, project-contained test manifests execute through
  the regular runner with fixture replay offline, isolated scratch state, expected-exit,
  local contract assertions, and JSON expected-output checks.
- [x] E5 foundation: `graph WORKFLOW --format mermaid` renders a deterministic validated DAG.
- [ ] E4 and E6-E9 remain in the dependency order defined by the plan.
