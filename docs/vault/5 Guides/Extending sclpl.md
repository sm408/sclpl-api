---
tags:
  - guide
---

# Extending sclpl

Four ways to add behaviour, in increasing order of ceremony.

## An ordinary script

For a project-local task that does not need a reusable registered name. Call it with
`sclpl python script.py [ARGS...]`, or use the `python` workflow function with `args` and JSON
`input`. It runs in the active environment, can import `sclpl`, and is trusted code rather than
a sandboxed extension.

## An operator

For something that is genuinely an operation on a type. `expr/ops/`.

```python
from sclpl.expr.dispatch import overload, generic

@overload("upper", str, summary="Uppercase.")
def upper(value: str) -> str:
    return value.upper()

@generic("coalesce", summary="The first non-null value.")
def coalesce(*values): ...
```

A **typed overload** beats a generic. Reach for `@generic` only when the type genuinely
does not matter — `eq`, `is_null`. Using it because a typed overload is inconvenient is
how a dispatch table becomes a pile of `isinstance` checks.

→ [[Expressions#Dispatch]]

## A function

For something with arguments and a signature. `functions/`, registered by
`ext/functions.py`.

```python
from sclpl.ext.functions import function

@function("summarise", version=1)
def summarise(data: Any, *, top: int = 5) -> dict[str, Any]:
    """One line, used as the summary in `fn list` and `--help`."""
    ...
```

Annotate everything. The schema, the help, the completion values, and the argument
coercion all come from the signature — see [[Built-in Functions#How registration works]].

Both `def` and `async def` work. A sync function that touches a `Table` is a
process-lane candidate; the lane assignment reads what is recorded at registration.

Register a name **once**. Two functions claiming one name is a startup error, not a
last-one-wins.

## A plugin

For a connector, an auth provider, a paginator, or a table backend — anything that needs
a manifest and a declared capability set.

```bash
sclpl plugin scaffold mything
sclpl plugin describe mything
```

That writes a plugin that **loads and runs immediately** — no fixes needed. Edit it.

Import from `sclpl.ext.api` and nothing else: that module is the promise, and everything
outside it may be rearranged between versions.

→ [[Plugins]] for discovery, the manifest, capabilities, and the bundled set.

## Rules of the road

- **No abstraction until the second caller** ([[Invariants#8 No abstraction until the second caller]])
- Reuse before writing. `records_of`, `refs_in`, and `did_you_mean` exist so there is one
  answer each
- Every error gets a remedy
- Watch [[The Line Budget]]. Deleting counts as progress, and the commit message should
  say what shrank
