---
tags:
  - decision
  - moc
---

# Invariants

Ten rules. **A violation is a review block, not a style note.** They are copied verbatim
from `CONTRIBUTING.md`, which is the contributor-facing summary; this note adds the reasoning
and the links.

## 1 stdout is data, stderr is interface

Progress never touches stdout. This is what makes `sclpl run wf --out report=- | jq`
work. `render/` writes only to stderr; `tables/io.py:_to_stdout` is the only thing that
writes to stdout, and only when a port is bound to `-`.

→ [[The Terminal Layer]]

## 2 Values keep their Python type end to end

Stringify only at an interpolation boundary. This is [[Why a Rewrite|defect 1]] made
impossible.

→ [[Typed Values]], [[Data Flow]]

## 3 The DAG is inferred from references

Reading `@orders` creates the dependency. Dependency lists are never hand-maintained —
`needs` may *add* an edge but can never remove one.

The subtle part: a control-flow body's references belong to its parent, because the body
is not a node until the parent runs. `run/compile_plan.py:references` handles this.

→ [[The DAG]], [[Control Flow]]

## 4 One writer to the terminal

Everything emits to a single queue; one task holds the handle. A worker pool writing
underneath a live region is how live regions get corrupted.

→ [[The Terminal Layer]]

## 5 The render ladder only descends

`full` → `simple` → `plain`. Never back up. A terminal that failed once is not trusted
again — climbing back would produce a display that flickers between modes.

→ [[The Terminal Layer#The ladder]]

## 6 Modes only subtract steps and override scalars

Never add, never rewire. Enforced by validating that the pruned IR is a subgraph of the
full IR.

→ [[Modes and Ports]]

## 7 Expressions evaluate over an allowlisted AST

Never `eval()`, never `exec()`. `expr/` has its own lexer, parser, and evaluator.

→ [[Expressions]]

## 8 No abstraction until the second caller

The old `contracts/` package had one implementation per interface. Do not recreate it.

The two abstractions that *do* exist earned it: `TableBackend` (so pandas is optional)
and the plugin ABI (so a plugin is not a fork).

## 9 Secrets never reach a log, a label, or a trace

Redaction lives in the reporter, keyed on the set of resolved secret values — so it
cannot be bypassed by a component that forgets to redact.

→ [[Secrets]]

## 10 `docs/reference/` is generated

Hand-editing it fails CI. This vault is not generated and may be hand-edited freely.
