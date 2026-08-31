---
tags:
  - package
---

# `run/`

Budget 3,600 (excluding `run/sclpll/`, which has its own — see [[The Line Budget]]).
The engine.

Full file table in [[Package Map#`run/` in detail]]. The notes that matter:

- [[The IR]] — `ir.py`, `compile_json.py`
- [[The DAG]] — `compile_plan.py`, `plan.py`
- [[Modes and Ports]] — `modes.py`, `ports.py`, and `preflight.py`
- [[The Scheduler]] — `schedule.py`
- [[Step Kinds]] — `execute.py`
- [[Control Flow]] — `control.py`
- [[Pagination]] — `paginate.py`
- [[Transport]] — `transport.py`, `retry.py`
- [[Errors and Exit Codes]] — `sclpl/errors.py`, which is *not* in this package

## `runner.py` is the only assembly point

One function everything else calls. `run`, the launcher, and (later) `runs replay` differ
in how they gather arguments, not in what happens afterwards — which is the only way
three entry points stay identical in behaviour.
