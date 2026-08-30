# SPEC

**`docs/cli-rebuild/SPEC.md`** — the normative implementation spec. It is not in this
vault; this note exists so links to it resolve and so its role is stated once.

> **The SPEC wins any disagreement.** If a note in this vault contradicts it, the note is
> stale. Fix the note and record it in [[Decision Log]].

## What is in it

| § | Subject |
|---|---|
| 4 | Repository layout, package by package |
| 6 | Dependency inference |
| 7 | The SCLPLL v2 grammar |
| 8 | Modes and ports |
| 9 | The expression language |
| 10 | Functions, tables, and the reference flattening behaviour |
| 12 | The scheduler, semaphores, lanes, liveness |
| 13 | HTTP transport |
| 15 | The CLI surface |
| 17 | The milestone plan and exit criteria |
| 19 | The line budget |

## Changing it

A [[Locked Decisions|locked decision]] needs an ADR in `docs/adr/` recording date,
reason, and migration impact. Everything else is an ordinary edit — but the SPEC and this
vault should not be allowed to drift, so an edit to one is a prompt to check the other.

## Related

- [[HANDOFF]] — where the work stands
- `docs/cli-rebuild/plan.html` — the argument and the evidence behind the constraints
