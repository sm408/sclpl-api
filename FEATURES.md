# FEATURES.md

This file describes product capabilities and architectural intent. It does not imply current implementation status unless a status is explicitly declared.

## Vision

SCLPLAPI is a local-first API workflow studio for developers, analysts, and integration-heavy users who need more than a request sender and less than a full enterprise orchestration platform.

## Design principles

- local-first
- Python-first
- human-hackable
- workflow-oriented
- export-centric
- extensible

## Status legend

- `PLANNED`: defined but not implemented
- `SCAFFOLDED`: documentation or structure exists
- `PARTIAL`: some implementation exists, feature incomplete
- `STABLE`: ready for normal use
- `DEFERRED`: intentionally postponed

## Architectural gravity

The project fundamentally revolves around:

- request execution
- workflow execution
- variable propagation
- Python extensibility
- export pipelines

## Capability matrix

### Request Engine

- HTTP request authoring: `PLANNED`
- auth modes (Bearer, Basic, API key): `PLANNED`
- response viewer: `PLANNED`
- history tracking: `PLANNED`

### Collections and Workspaces

- collection tree: `PLANNED`
- saved requests: `PLANNED`
- workspaces: `PLANNED`

### Environments and Variables

- environment switching: `PLANNED`
- scoped variable resolution: `PLANNED`
- runtime variable propagation: `PLANNED`

### Function System

- filesystem-discovered Python functions: `SCAFFOLDED`
- pre-request hooks: `PLANNED`
- post-response transformers: `PLANNED`
- auth token generators: `PLANNED`

### Workflow Engine

- sequential chains: `PLANNED`
- foreach loops: `PLANNED`
- conditional execution: `PLANNED`
- retries: `PLANNED`
- dependency graph execution: `PLANNED`
- visual builder: `DEFERRED`

### Export Pipeline

- JSON export: `PLANNED`
- CSV export: `PLANNED`
- Excel workbook generation: `PLANNED`
- reusable transformation pipelines: `PLANNED`

### Plugins

- plugin discovery: `PLANNED`
- manifests and lifecycle hooks: `PLANNED`
- internal extension points: `PLANNED`

### Analytics

- summaries and grouping: `PLANNED`
- lightweight pivot/report outputs: `PLANNED`
- dashboards: `DEFERRED`

### Storage

- SQLite-first persistence: `PLANNED`
- versioned schema migrations: `PLANNED`
- backup/shareable data model: `PLANNED`

## MVP definition

The first usable milestone should include only:

- request execution
- collections
- environments
- history
- CSV batch execution
- basic function hooks
- JSON/CSV exports

## Future scope

- workflow graphs
- typed event bus
- plugin ecosystem
- analytics pane
- secrets vault
- visual orchestration

## Non-goals for early stages

- Electron rewrite
- cloud account system
- mandatory telemetry
- heavy multi-user platform design
- AI-first opaque execution

