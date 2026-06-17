# ARCHITECTURE.md

## Project identity

SCLPLAPI is a local-first Python application with a layered execution architecture. The architecture should be strong enough for later headless execution, but simple enough for a single-user local-first product.

## Layer model

```text
UI
  -> Services
    -> Core
      -> Storage / Infrastructure
```

### UI

Owns:

- rendering
- interaction
- progress display
- workspace navigation

Must not own:

- HTTP execution
- workflow engine logic
- persistence rules

### Services

Own:

- use-case orchestration
- request submission coordination
- workflow lifecycle orchestration
- event publication for side effects

### Core

Owns:

- request execution models
- workflow graph logic
- variable resolution
- function context contracts
- export pipeline contracts

Core must remain UI-independent.

### Storage / Infrastructure

Owns:

- SQLite access
- schema migrations
- import/export file IO
- HTTP transport adapters
- plugin and function discovery IO

## Primary subsystems

- request engine
- environment and variable system
- function runtime
- workflow engine
- event bus
- export engine
- plugin system
- storage and migrations

## Architectural commitments

- design workflow runtime internally as a graph engine even if the first UI only exposes sequential chains
- treat function and plugin contracts as stable boundaries
- use typed, explicit execution context instead of hidden globals
- keep event bus lightweight and in-process
- prefer filesystem-discoverable extensibility

## Deferred complexity

These are intentionally postponed:

- visual node editor
- remote sync
- distributed execution
- enterprise role systems

