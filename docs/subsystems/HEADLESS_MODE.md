# Headless Mode

SCLPLAPI headless mode allows request, workflow, and export execution without the interactive UI.

## Intended use

- automation
- CI smoke runs
- repeatable local task execution
- export generation

## Minimum headless capabilities

- load project/workspace data
- resolve variables and environments
- run a request or workflow
- emit logs and structured results
- generate export artifacts

## Constraints

- headless mode uses the same core runtime as the UI path
- no parallel implementation of business logic
- output must be scriptable and machine-readable

Primary references:

- `RUNTIME_MODEL.md`
- `WORKFLOW_ENGINE.md`
- `EXPORT_ENGINE.md`
