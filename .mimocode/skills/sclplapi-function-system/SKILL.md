---
name: sclplapi-function-system
description: Use when building or reviewing the Python function runtime, execution context, metadata, and low-ceremony extensibility model.
---

## Purpose

Preserve low-ceremony Python extensibility. Keep execution context explicit and stable. Protect filesystem-driven discovery as a core feature.

## When to use

- function discovery implementation
- function metadata parsing
- pre-request hooks
- post-response transformers
- auth-token generators
- execution context design

## Rules

- functions discovered recursively from filesystem
- minimal contract: docstring metadata + `run(ctx)` entrypoint
- context object exposes: request, response, workflow, environment, variables, runtime, config, metadata, batch_row
- function contracts are user-facing APIs
- trusted local execution model (no sandboxing unless explicitly added)

## Key files

- `FUNCTION_SYSTEM.md`
- `requirements/extensibility_requirements.md`
- `rules/runtime-rules.md`
- `docs/subsystems/functions.md`
