# Runtime Model

The SCLPLAPI runtime model defines how requests, workflows, functions, plugins, variables, and exports execute.

## Runtime layers

- orchestration services
- core execution engine
- storage-backed persistence
- optional UI observers

## Execution model

- resolve environment and variables
- build execution context
- run request/function/node
- emit runtime events
- persist run outcome
- optionally export results

## Required runtime properties

- cancellation support
- retry awareness
- deterministic node transitions
- stable structured errors

## Deliberate exclusions

- UI-driven hidden side effects
- storage calls from the UI bypassing services
- plugin mutation of private runtime state

Primary references:

- `ARCHITECTURE.md`
- `WORKFLOW_ENGINE.md`
- `EVENT_BUS.md`
