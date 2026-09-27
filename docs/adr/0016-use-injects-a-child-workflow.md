# ADR 0016 — `use` injects a child workflow into the parent's graph

- **Date:** 2026-09-27
- **Status:** accepted
- **Amends:** [ADR 0008](0008-budget-remote-resource-integration.md) (the `run` budget)

## Decision

`use <workflow> [mode=<name>] [name=value ...]` runs another workflow as a step. It is
not a nested run with its own scheduler. The child's kept top-level steps become nodes
of the parent's graph under `<step>::use::<child step>`, the same runtime expansion a
`foreach` uses (`Scheduler.expand`), wired by the edges of the child's own plan. The
parent's global, host, and tag ceilings, the memory governor, the host policy, and the
transport therefore govern the child's requests exactly as if they had been written in
the parent. The child's own `@limits` do not apply; the run has one set of limits.

**Binding.** Each argument names one of the child's `@var`s (the value overrides the
default, like `--var`) or one of its `@input`s (the value is bound in memory under that
name, not read from a file). Arguments are resolved in the parent's scope, so they keep
their types and create dependencies like any other reference. An optional input that
is not passed is `null`.

**Isolation.** Child expressions evaluate against an empty store of their own and a
frame with no parent: a child step called `fetch` never sees or frees the parent's
`fetch`, and the parent sees only the step's value. Nodes created inside a child keep
only decorated names in their `reads`, for the same reason.

**Result.** A child that declares outputs produces `{port: value}`, where the value is
what that port's `-> port` step would have written. A used workflow never writes its
declared outputs; the caller decides what to do with them. A child with no declared
outputs produces its last kept step's value.

**Resolution and validation.** The workflow is resolved like `sclpl run` resolves its
argument, with the using file's directory (and its `workflows/`) searched first.
Preflight resolves every kept `use` step recursively and reports, naming the step: a
missing workflow, an unknown argument, a missing required input, anything the child's
own preflight rejects (including its mode's closure check), and any chain of `use` that
leads back to a workflow already on it. A `use` pruned by the parent's mode is not
resolved at all.

**History.** Child steps are nodes of the parent run, so they appear in its step
records under their decorated ids; there is no separate run row.

## Rejected alternatives

- *Call `run_workflow` for the child inside the step.* Simple, but the step would hold a
  worker and a concurrency slot while a second scheduler ran with its own ceilings --
  the nested-`gather` shape SPEC §12 rules out.
- *Inline the child's steps into the parent IR at parse time.* It would break
  `fmt`/`convert` round-tripping and make two uses of one child collide on step ids.
- *Bind the child's outputs to files.* Possible later as `name=path` arguments; values
  in memory are what a composed workflow almost always wants next.

## Budget

`run` rises from 5,000 to 5,250 lines and the total from 26,720 to 26,970. The feature
adds `run/subflow.py` and the dispatch, scope, and collection changes in `execute.py`,
`preflight.py`, and `runner.py`: about 150 counted lines, measured at 5,151. `run` had 54
lines of headroom, so the prior cap would reject tested behaviour rather than constrain
unplanned growth; the rise leaves roughly 100 lines.
