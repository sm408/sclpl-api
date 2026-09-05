# ADR 0005 — Budget project test-manifest discovery

- **Date:** 2026-09-05
- **Status:** accepted
- **Amends:** [ADR 0004](0004-budget-contracts-package.md)

## Decision

Project test-manifest parsing and discovery live in `sclpl/testing/` with an explicit
700-line budget. The total source budget rises from 19,100 to 19,800 lines.

Test manifests are schema-versioned TOML declarations. They name a workflow, optional
environment and inputs, a project-local fixture path, expected exit, assertions, and
expected outputs. Discovery and validation do not execute a workflow.

## Consequences

The test execution slice receives already validated, project-contained inputs. Fixture
paths that escape the project are rejected before any execution side effect. This
separation permits an offline-by-default runner with isolated state and outputs in the
next slice without introducing a second manifest parser.
