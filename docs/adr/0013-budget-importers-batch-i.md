# ADR 0013: Budget `sclpl/importers` for Batch I

## Decision

Add `sclpl/importers/` as its own 2,600-line budget, raise `sclpl/cli` from 2,450
to 2,600 lines, and raise the total source budget from 23,470 to 26,120 lines.

## Rationale

Batch I (`docs/cli-rebuild/UNIFIED-UPGRADE-PLAN.md`) adds three independent
import adapters -- curl (I1, landed: `shell.py` tokenizes POSIX and Windows
argv without ever invoking a shell, `curl.py` parses and renders a workflow),
OpenAPI (I2), and Postman (I3) -- plus notification hooks (I4) and CI output
templates (I5). `importers` earns its own budget the same way `packages` did
for Batch H: self-contained functionality (only `importers -> errors` as a
`sclpl/` edge) that would otherwise inflate an unrelated package. 2,600 lines
covers I1 (delivered, ~400 lines) with headroom for I2's and I3's format
parsers, which are larger by nature (a real OpenAPI 3.x or Postman v2.1
document has far more structure than a curl command line). The `cli` bump
covers the small `--from curl` addition to the existing `import` command plus
whatever I2/I3/I5 still need.
