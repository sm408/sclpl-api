# SCLPLAPI

SCLPLAPI is a local-first, Python-first API workflow studio.

The project starts from the earlier PyPostman concept and is renamed here to a distinct, implementation-ready identity: `SCLPLAPI`.

## What it is

SCLPLAPI is intended to sit between:

- an API client
- a workflow runner
- a lightweight transformation engine
- an export/reporting workbench

It is not just a request sender. The long-term center of gravity is:

- request execution
- variable and environment resolution
- workflow orchestration
- Python-native extensibility
- export pipelines

## Current repository state

This repository is documentation-first. It contains the architecture, requirements, rules, and MiMo scaffolding needed to build SCLPLAPI. It does not yet contain the full application implementation.

## Source-of-truth documents

Start here:

- `AGENTS.md`
- `FEATURES.md`
- `ARCHITECTURE.md`
- `WORKFLOW_ENGINE.md`
- `FUNCTION_SYSTEM.md`
- `PLUGIN_SDK.md`
- `EXPORT_ENGINE.md`
- `DATABASE_AND_MIGRATIONS.md`
- `UI_UX_GUIDE.md`
- `CODING_STANDARDS.md`
- `TESTING_STRATEGY.md`

## Repository structure

```text
AGENTS.md                      agent and contributor instructions
FEATURES.md                    capability matrix and status
ARCHITECTURE.md                layered execution architecture
WORKFLOW_ENGINE.md             workflow runtime design
FUNCTION_SYSTEM.md             Python extensibility layer
PLUGIN_SDK.md                  plugin contracts and lifecycle
EXPORT_ENGINE.md               export pipeline subsystem
DATABASE_AND_MIGRATIONS.md     SQLite-first persistence doctrine
UI_UX_GUIDE.md                 UI responsibilities and constraints
CODING_STANDARDS.md            formatting, typing, async rules
TESTING_STRATEGY.md            test priorities and philosophy
mimocode.json                  MiMo project config

requirements/                  implementation requirement sets
rules/                         additional MiMo instruction files
docs/
  architecture/                architectural concept docs
  subsystems/                  subsystem-specific guides
  planning/                    roadmap, non-goals, dev strategy
  decisions/                   architecture decision records
  adr/                         detailed ADR files
.mimocode/                     project-local MiMo skills, agents, tools
```

## Intended future application skeleton

```text
app/
  core/
  services/
  storage/
  ui/
functions/
data/
docs/
requirements/
```

## Build doctrine

- local-first
- human-hackable
- Python-first
- strict core, flexible feature layer
- runtime before visual builder
- workflows before "smart" automation
