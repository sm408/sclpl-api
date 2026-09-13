# ADR 0012: Budget `sclpl/cli` for Batch H package commands

## Decision

Increase the `sclpl/cli` code budget from 2,300 to 2,450 lines and raise the total
source budget from 23,320 to 23,470 lines.

## Rationale

H3's `sclpl package list/show/verify/remove/update` commands (`cli/package_cmd.py`)
push `cli` 14 lines over its existing budget. 150 lines of headroom covers those
plus whatever CLI surface H4 (registry client) and H5 (registry release workflow)
still need, without another ADR for each one.
