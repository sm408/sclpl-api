---
name: sclplapi-request-engine
description: Use when building request execution, environments, variables, history, and CSV batch behavior in SCLPLAPI.
---

## Purpose

Guide request-engine work toward a solid MVP. Keep environment and variable resolution explicit. Keep batch execution scoped and deterministic.

## When to use

- HTTP request model design
- auth handling (Bearer, Basic, API key)
- environment switching logic
- request history tracking
- CSV batch execution
- response viewer contracts

## Rules

- request execution lives in core, not UI
- environment switching must not mutate request definitions
- variable resolution follows explicit precedence: step > runtime > batch_row > workflow > environment > global
- history must be persistent and queryable

## Key files

- `FEATURES.md`
- `requirements/functional_requirements.md`
- `requirements/mvp_requirements.md`
- `docs/subsystems/VARIABLE_SYSTEM.md`
