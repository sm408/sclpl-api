---
tags:
  - package
---

# `ext/`

Budget 700. How anything outside the engine gets in.

| File | Job |
|---|---|
| `functions.py` | The `@function` decorator, `Registered`, schema generation, coercion |
| `plugins.py` | Entry-point discovery, manifest, ABI, capabilities #todo *(M8)* |

→ [[Built-in Functions#How registration works]], [[Extending sclpl]]

## Signatures are the interface

`Registered` derives the JSON Schema, the help text, the completion values, and the
argument coercion from annotations alone. Nothing is declared twice, so nothing can
drift.
