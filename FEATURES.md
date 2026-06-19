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

- HTTP request authoring: `STABLE`
- auth modes (Bearer, Basic, API key): `STABLE`
- response viewer: `STABLE`
- history tracking: `STABLE`

### Collections and Workspaces

- collection tree: `STABLE`
- saved requests: `STABLE`
- workspaces: `PLANNED`

### Environments and Variables

- environment switching: `STABLE`
- scoped variable resolution: `STABLE`
- runtime variable propagation: `STABLE`

### Function System

- filesystem-discovered Python functions: `STABLE`
- pre-request hooks: `STABLE`
- post-response transformers: `STABLE`
- auth token generators: `STABLE`

### Workflow Engine

- sequential chains: `STABLE`
- foreach loops: `STABLE`
- conditional execution: `STABLE`
- retries: `STABLE`
- dependency graph execution: `STABLE`
- visual builder: `DEFERRED`

### Export Pipeline

- JSON export: `STABLE`
- CSV export: `STABLE`
- Excel workbook generation: `STABLE`
- reusable transformation pipelines: `PLANNED`

### Plugins

- plugin discovery: `STABLE`
- manifests and lifecycle hooks: `STABLE`
- internal extension points: `STABLE`

### Analytics

- summaries and grouping: `PLANNED`
- lightweight pivot/report outputs: `PLANNED`
- dashboards: `DEFERRED`

### Storage

- SQLite-first persistence: `STABLE`
- versioned schema migrations: `SCAFFOLDED`
- backup/shareable data model: `PLANNED`

### SCLPLL Language

- scripting language: `STABLE`
- compiler/decompiler: `STABLE`
- dot notation: `STABLE`
- loops (@foreach, @repeat): `STABLE`
- conditional execution (@when): `STABLE`
- rate limiting (@semaphore): `STABLE`

### TUI

- terminal user interface: `STABLE`
- interactive menu: `STABLE`
- live workflow execution: `STABLE`
- function browser: `STABLE`

### Web GUI

- FastAPI backend: `STABLE`
- SPA frontend: `STABLE`
- request editor: `STABLE`
- collections view: `STABLE`
- workflow runner: `STABLE`
- flow builder: `STABLE`
- function browser: `STABLE`
- history viewer: `STABLE`
- settings panel: `STABLE`

### Tools Library

- workflow validator: `STABLE`
- function linter: `STABLE`
- sclpll formatter: `STABLE`
- performance analyzer: `STABLE`

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
