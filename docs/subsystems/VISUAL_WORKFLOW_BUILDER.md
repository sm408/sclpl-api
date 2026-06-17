# Visual Workflow Builder

The visual workflow builder is a later-stage interface over the same graph runtime.

## Position in roadmap

- not an MVP dependency
- built after sequential and graph execution are stable
- must never define behavior unavailable in headless/runtime form

## Design rules

- the graph model is the source of truth
- the builder edits explicit node and edge data
- builder features must degrade to textual/configured forms

## MVP for the builder

- visualize existing workflows
- inspect node state
- edit graph wiring without inventing new runtime semantics

Primary references:

- `WORKFLOW_ENGINE.md`
- `WORKFLOWS.md`
- `ROADMAP.md`
