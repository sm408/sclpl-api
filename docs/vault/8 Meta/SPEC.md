---
tags:
  - meta
---

# SPEC

`docs/cli-rebuild/SPEC.md` is the normative implementation specification. It is not in this
vault; this note explains its role and points to the current project status.

> **The SPEC wins any disagreement.** If a note in this vault contradicts it, the note is stale.
> Fix the note and record the change in [[Decision Log]].

## What is in it

| Section | Subject |
|---|---|
| 4 | Repository layout, package by package |
| 6 | Dependency inference |
| 7 | The SCLPLL v2 grammar |
| 8 | Modes and ports |
| 9 | The expression language |
| 10 | Functions, tables, and reference flattening |
| 12 | Scheduler, semaphores, lanes, and liveness |
| 13 | HTTP transport |
| 15 | The CLI surface |
| 17 | Milestones and exit criteria |
| 19 | The line budget |

## Changing it

A [[Locked Decisions|locked decision]] needs an ADR in `docs/adr/` recording the date, reason,
and migration impact. Everything else is an ordinary edit, but the SPEC and this vault should
remain aligned.

## Related

- [[Milestone Status]] - completed milestones, gates, and deliberate limitations
- `docs/cli-rebuild/plan.html` - the argument and evidence behind the constraints
