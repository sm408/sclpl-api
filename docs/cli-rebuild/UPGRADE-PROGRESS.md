# Unified upgrade progress

This checklist records implementation evidence for
[the unified upgrade plan](UNIFIED-UPGRADE-PLAN.md). A checked item has code and focused
verification behind it; unchecked work remains release scope.

## Batch A

- [x] A2 format/version ownership: ADR 0003 defines project schema handling and the
  policy for every later persistent format.
- [x] A4 architectural gates: budget checking refuses unbudgeted packages and layering
  checking detects directed cycles of any length.
- [ ] A1 compatibility baseline and regression fixtures.
- [ ] A3 metadata-first plugin activation.
- [ ] A5 credential-sink audit and regression helpers.

## Batch B

- [x] B1 strict manifest discovery and environment precedence.
- [x] B2 project initialization, `project check`, and `workflow list`.
- [x] B3 local environment selection and safe context reporting.
- [ ] B4-B6 authentication providers.

## Later batches

- [ ] C through J remain in the dependency order defined by the plan.
