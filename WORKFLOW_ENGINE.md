# WORKFLOW_ENGINE.md

## Purpose

The workflow engine turns SCLPLAPI from a request sender into an API automation runtime.

## Target progression

1. sequential chains
2. foreach loops and variable propagation
3. conditional execution and retries
4. dependency graph execution
5. visual builder

## Core concepts

### Node

A unit of execution such as:

- request
- function
- export
- transformer

### Edge

A dependency link between nodes.

### Runtime context

Shared execution state containing:

- variables
- step outputs
- loop values
- environment values

## Required capabilities

- request referencing
- variable propagation
- conditional execution
- retries based on status/body rules
- foreach loops
- branch support
- resumable state design

## Variable precedence

Recommended order:

1. step
2. runtime
3. batch row
4. workflow
5. environment
6. global

## Execution rules

- runtime design first, visual builder later
- graph-aware internals even for sequential MVP
- deterministic context mutation
- explicit cancellation and timeout support
- no hidden cross-step magic

## Deferred items

- drag/drop builder
- distributed scheduling
- long-running daemon orchestration

