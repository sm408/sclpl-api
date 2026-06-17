# AGENTS.md

Project name: `SCLPLAPI`

Historical note: the project originated from the working title `PyPostman`. Use `SCLPLAPI` for all new documentation, code, naming, and agent outputs.

## Mission

SCLPLAPI is a programmable, local-first API workflow studio with Python-native extensibility.

The project is not merely:

- a Postman clone
- a REST request tester
- a generic CRUD desktop app

It is a platform for:

- request execution
- workflow chaining
- transformation pipelines
- export orchestration
- user-authored Python functions

## Non-negotiable principles

- Local-first: no mandatory cloud dependency.
- Human-hackable: filesystem-visible configuration and extension points.
- Python-first: prefer Python runtime and extension design over JS-heavy architecture.
- Strict core, flexible feature layer: preserve discipline in engine and contracts.
- Runtime first: build execution and workflow integrity before visual workflow builders.

## Current repo reality

This repo is documentation-first at the moment. Do not pretend unfinished features already exist.

All docs and code changes must clearly distinguish:

- implemented
- scaffolded
- planned
- deferred

## Required reading order for agents

1. `README.md`
2. `FEATURES.md`
3. `ARCHITECTURE.md`
4. `WORKFLOW_ENGINE.md`
5. `FUNCTION_SYSTEM.md`
6. `PLUGIN_SDK.md`
7. `EXPORT_ENGINE.md`
8. `DATABASE_AND_MIGRATIONS.md`
9. `CODING_STANDARDS.md`
10. relevant files in `requirements/`

## Architecture rules

- Preserve layer direction: `ui -> services -> core -> storage`.
- Do not let UI own workflow logic, persistence logic, or HTTP transport logic.
- Keep the core execution engine UI-independent.
- Treat plugin and function contracts as user-facing APIs.
- Prefer typed contracts and explicit context objects.

## Product rules

- Workflows are a core architectural commitment.
- Event bus support is required, but it must stay lightweight and in-process.
- The function system is a first-class platform capability, not a convenience add-on.
- Exports are pipelines, not “save as” utilities.
- Visual workflow builders are deferred until runtime design is stable.

## Delivery rules

- Update docs when architecture changes.
- Add ADRs for meaningful architecture decisions.
- Avoid speculative abstractions not backed by the current roadmap.
- Avoid trademark-risk references in naming, branding, or UI copy.

