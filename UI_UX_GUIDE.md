# UI_UX_GUIDE.md

## UI role

The UI is the interaction shell around the execution runtime.

## UX goals

- fast
- keyboard-friendly
- modern but not flashy
- workspace-oriented
- readable under heavy API usage

## UI responsibilities

- request editing
- response viewing
- workflow inspection
- export initiation
- progress visibility

## UI must not do

- direct HTTP transport work
- storage mutations outside service boundaries
- own workflow execution logic

## Sequencing rule

Prefer runtime maturity before visual complexity. The workflow builder UI is deferred until the workflow runtime is stable.

