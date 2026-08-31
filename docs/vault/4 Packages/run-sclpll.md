---
tags:
  - package
---

# `run/sclpll/`

Budget 1,200. The SCLPLL v2 surface: lexer, parser, canonical emitter.

Budgeted separately from [[run]] because it grows with the **grammar**, not with what the
runner does — [[The Line Budget]], ADR 0002.

| File | Job |
|---|---|
| `lex.py` | Tokens, indentation (INDENT/DEDENT), `split_args`, `unquote` |
| `parse.py` | Tokens → IR |
| `emit.py` | IR → canonical SCLPLL: stable ordering, two-space indent |

## The grammar stays small

An unknown verb is **not** a parse error. It is looked up in the function and connector
registries, which is what lets a plugin contribute vocabulary without touching
`parse.py`.

## `split_args`

Deceptively load-bearing. It must keep four things intact as single arguments: a quoted
string, a `{{...}}` interpolation, a JSON object, and a JSON array. `{{` is read as
interpolation before a bare `{`, so an object literal cannot start with another object.

Both a missing JSON-bracket depth and an over-eager `=` split were real bugs — see
[[Decision Log]].

## v1 is not readable

[[Locked Decisions#4 SCLPLL v2 is a clean break]]. A v1 file fails at its first directive
with a message saying so, which is better than importing it wrong.
