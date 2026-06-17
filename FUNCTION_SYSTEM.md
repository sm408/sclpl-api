# FUNCTION_SYSTEM.md

## Purpose

The function system is the lightweight Python extensibility layer for SCLPLAPI.

## Principles

- low ceremony
- Python-first
- human-hackable
- composable
- filesystem-driven

## Function types

- `pre_request`
- `post_response`
- `auth_token`

Future candidates:

- `transformer`
- `analytics`
- `validator`
- `exporter`
- `workflow_node`

## Discovery model

Functions should be discovered recursively from a filesystem directory tree, with the filesystem acting as the source of truth.

## Minimal contract

```python
"""
@name: Example Function
@type: post_response
@version: 1
"""

def run(ctx):
    return ctx
```

## Execution context

The shared `ctx` object should expose at least:

- `request`
- `response`
- `workflow`
- `environment`
- `variables`
- `runtime`
- `config`
- `metadata`
- `batch_row`

## Contract rules

- function contracts are user-facing APIs
- breaking changes require schema/version strategy
- secret config must be masked and handled deliberately
- functions may mutate relevant context, not unrelated runtime state

## Security model

Current assumption: trusted local execution.

Optional sandboxing may arrive later, but unrestricted local power is part of the platform identity.

