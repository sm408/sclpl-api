---
name: sclplapi-testing
description: Use when writing tests, planning test coverage, or validating core engine, workflow, function, and export behavior.
---

## Purpose

Test determinism over UI cosmetics. Test behavior at boundaries. Isolate async and cancellation behavior. Prefer focused subsystem tests.

## When to use

- writing unit tests for core modules
- planning test coverage priorities
- validating workflow execution
- testing function contracts
- testing export determinism
- migration testing

## Priority order

1. variable resolution
2. workflow execution
3. function execution contracts
4. plugin loading and compatibility
5. exporters and transformations
6. migrations
7. retry and timeout behavior

## Rules

- pytest for automated validation
- core engine: high coverage
- workflow runtime: very high coverage
- storage and migrations: high coverage
- UI: minimal sanity coverage

## Key files

- `TESTING_STRATEGY.md`
- `CODING_STANDARDS.md`
- `requirements/mvp_requirements.md`
