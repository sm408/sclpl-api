# The DAG

`run/compile_plan.py` builds the specs; `run/plan.py` validates and scores them.

## Inference, not declaration

[[Invariants#3 The DAG is inferred from references]]. Every string in a step's
configuration is scanned for `@name`. `expr/refs.py:refs_in` is the single point that
does the scanning, and it handles all three shapes:

- a whole expression — `count(@fetch.body)`
- an interpolation — `"{{ @fetch.body.total }} rows"`
- a bare reference — `@fetch.body.data`

**This is the bug that hides.** Before `expr/refs.py` existed, the scanner only handled
`{{}}` and strings *starting* with `@`, so `let count(@fetch.body)` produced no edge and
the step ran before its dependency. Nothing failed loudly; the value was simply missing.
Invariant 3 was broken silently. One function, one call site, no second scanner.

## Nested bodies

A control-flow body's steps are **not** nodes. They become nodes when the parent runs
and knows how many copies there are — once per element for a `foreach`, once per pass
for a `while`, not at all for the branch an `if` did not take.

Two consequences, both in `compile_plan.py`:

- `_spec` records the body's names under `produces`, so a later step reading `@double`
  waits for the loop — which is the only honest answer before the loop has run.
- `references()` folds a body's references into the parent, minus the names the body
  supplies itself (the loop variable, and sibling step ids). Otherwise `foreach @ids`
  whose body reads `@config` would run before `config` existed.

→ [[Control Flow]]

## What `build()` guarantees

`run/plan.py:build` raises rather than returning a broken graph:

- two steps producing the same name
- a reference to a name nothing produces (with the nearest match suggested)
- a declared `needs` naming a step that does not exist
- a cycle (naming the steps in it)

Then `_score_critical_paths` computes, for each node, the longest weighted path to a
leaf. The scheduler pops the highest first, so the longest chain starts earliest.

## Weights

Rough, and only the ratios matter: `http` 10.0, `use` 10.0, `foreach` 5.0, `while` 5.0,
`fn` 2.0, `parallel` 1.0, `let` 0.1, `if` 0.1, `gate` 0.1. An HTTP request dominates a
local expression by orders of magnitude, and scheduling should reflect that before it
has any measurements to go on.

## The Node

```python
class Node:
    id: str
    reads: frozenset[str]       # every one is an edge
    needs: frozenset[str]       # node ids to wait for
    dependents: frozenset[str]  # node ids waiting on this
    tags / host / lane
    critical_path: float
    weight: float
    binds: str | None           # the store name this publishes under
```

`binds` exists for [[Control Flow]]: a `foreach` publishes nothing useful itself, and
the barrier after its iterations publishes the loop's result under the loop's name.
