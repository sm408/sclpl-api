---
tags:
  - concept
---

# Errors and Exit Codes

An exit code is a message to a script. Each one means a different thing should happen
next, which is why there are eight rather than two.

| Code | Name | Means | You should |
|---:|---|---|---|
| 0 | `EXIT_OK` | Everything ran | — |
| 1 | `EXIT_STEP_FAILED` | A step failed | Look at the step; retry may help |
| 2 | `EXIT_USAGE` | The command line was wrong | Fix the invocation |
| 3 | `EXIT_VALIDATION` | Preflight refused it | Fix the workflow; nothing ran |
| 4 | `EXIT_ASSERTION` | The **data** was wrong | Look at the data, not the request |
| 5 | `EXIT_CACHE_MISS` | `--from-cache` had nothing | Run without it once |
| 6 | `EXIT_UNKNOWN_TARGET` | No such workflow | Check the name; a suggestion is printed |
| 130 | `EXIT_INTERRUPTED` | Ctrl-C | — |

**3 and 4 are the two that earn their keep.** 3 means nothing happened, so re-running
after a fix costs nothing. 4 means the requests succeeded and the answers were wrong,
which is an entirely different investigation from a 500.

## Where they live

`sclpl/errors.py`, at the top of the package rather than inside `run/`. Every package
raises these, so it is shared vocabulary rather than part of the engine — and while it
was inside `run/`, `run/` looked like something the whole tree depended on when what the
tree depended on was one leaf. → [[Architecture Measured]]

The exit codes live there too, for the same reason in the other direction. They used to
be in `cli/options.py`, which meant the engine imported the command line to know what
number to fail with.

## The shape of a diagnostic Every error carries a message, optionally a location, and a list of
**remedies**. A message without a remedy is a bug report about the message.

```
error [merge_products]: cannot join on 'sku': the left table has no such column
  - left columns: id, customer_id, total, lines, customer_name, customer_region_id
```

Rules the codebase holds itself to:

- Name the thing that was wrong **and** what was there instead
- Suggest the nearest valid name when there is one (Damerau-Levenshtein; see
  [[Expressions#Paths]])
- List the alternatives when the set is small and closed
- Never say "unsupported" or "invalid" without saying what *is* supported

## The hierarchy

`SclplError` is the base and carries `exit_code`. Notable subclasses:

- `ValidationError` → 3. Anything preflight catches
- `StepFailed` → 1. A step did not produce a value
- `AssertionFailed` → 4. An `assert` or an `assert_*` function
- `TypeDispatchError` → 1. A function or operator got the wrong shape
- `UnknownReference` / `PathError` → the reference did not resolve
- `MissingExtra` → an optional dependency is not installed

## Nothing shows a traceback

A `SclplError` reaching `cli/app.py:entrypoint` is printed as the diagnostic it is and
the process exits with its code. Individual commands catch it too, but the entrypoint is
the backstop: a message written to be read should never arrive as a stack trace with the
message buried in the middle of it.

## Wrapping

A function raising something that is *not* a `SclplError` is wrapped with the step id
and the function name. A bare `AttributeError: 'str' object has no attribute 'get'`
names Python; `step 'shape_products' failed inside rename(): AttributeError: …` names the
workflow.
