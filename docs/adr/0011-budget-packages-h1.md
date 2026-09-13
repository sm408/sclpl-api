# ADR 0011: Budget `sclpl/packages` for Batch H

## Decision

Add `sclpl/packages/` as its own 1,600-line budget and raise the total source budget
from 21,720 to 23,320 lines.

## Rationale

Batch H (`docs/cli-rebuild/UNIFIED-UPGRADE-PLAN.md`) adds reproducible package
build (H1), validated install (H2), a shared registry client (H4), and their
supporting lifecycle. This is new, self-contained functionality with no runtime
dependency from the rest of `sclpl/` -- only `packages -> project` and
`packages -> errors` edges exist, so it earns its own budget rather than inflating
`project` or `cli`. 1,600 lines covers H1 (implemented: `build.py`, ~120 lines) with
headroom for H2 and H4 landing in the same package; H5 (registry release workflow)
is CI/publishing tooling outside `sclpl/` and does not draw on this budget. H3
(plugin lifecycle) extends the existing `ext`/`cli` packages and will need its own,
separate budget increase when it lands.
