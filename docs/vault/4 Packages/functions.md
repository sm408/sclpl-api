---
tags:
  - package
---

# `functions/`

Budget 1,200. The 43 built-ins.

| File | Family |
|---|---|
| `io_fns.py` | `save_*`, `read_*`, `glob_read`, `convert`, `flatten`, `explode`, `to_table`, `normalize` |
| `shape_fns.py` | `join`, `merge`, `concat`, `sort_by`, `dedupe`, `group_agg`, `pivot`, `select`, `rename`, `head`, `infer_schema`, `cast_schema` |
| `diagnostics.py` | `assert_*`, `profile`, `describe`, `sample` |

→ [[Built-in Functions]]

Loaded by `sclpl/bootstrap.py`, which registers built-ins **before** plugins so a plugin
that shadows one is doing it deliberately and can be reported as such.
