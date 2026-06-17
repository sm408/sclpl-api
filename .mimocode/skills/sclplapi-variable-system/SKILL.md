---
name: sclplapi-variable-system
description: Use when implementing variable resolution, scoping, precedence, and environment-aware value propagation.
---

## Purpose

Resolve authored values into runtime-ready execution data. Make resolution traceable and precedence explicit. Produce actionable errors on missing variables.

## When to use

- variable resolution logic
- environment value merging
- secret value handling
- workflow context variable propagation
- function/plugin-produced variable injection

## Rules

- precedence must be explicit: step > runtime > batch_row > workflow > environment > global
- resolution must be traceable
- missing variables produce actionable errors
- secret values remain redactable in logs and reports

## Key files

- `docs/subsystems/VARIABLE_SYSTEM.md`
- `WORKFLOW_ENGINE.md`
- `FEATURES.md`
- `requirements/functional_requirements.md`
