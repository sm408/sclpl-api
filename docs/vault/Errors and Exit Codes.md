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

## The shape of a diagnostic

`run/errors.py`. Every error carries a message, optionally a location, and a list of
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

## Wrapping

A function raising something that is *not* a `SclplError` is wrapped with the step id
and the function name. A bare `AttributeError: 'str' object has no attribute 'get'`
names Python; `step 'shape_products' failed inside rename(): AttributeError: …` names the
workflow.
