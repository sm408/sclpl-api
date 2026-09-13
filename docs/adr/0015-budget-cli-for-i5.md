# ADR 0015: Budget `sclpl/cli` for I5

## Decision

Increase the `sclpl/cli` code budget from 2,600 to 2,700 lines and raise the
total source budget from 26,620 to 26,720 lines.

## Rationale

I5's `--junit`/`--json`/`--html` options on `sclpl test run` and the new
`sclpl project ci-template` command push `cli` 25 lines over its existing
budget. 100 lines of headroom covers those plus whatever Batch J's own CLI
surface still needs.
