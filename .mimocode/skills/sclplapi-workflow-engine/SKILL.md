---
name: sclplapi-workflow-engine
description: Use when designing or implementing workflow chains, dependency graphs, retries, loops, and variable propagation for SCLPLAPI.
---

## Purpose

Keep workflow work aligned with runtime-first sequencing. Reinforce graph-capable internals even when UI is still sequential. Guard against premature visual-builder complexity.

## When to use

- step referencing and chaining
- runtime context design
- sequential chain implementation
- foreach loop design
- retry and conditional execution rules
- dependency graph execution
- variable propagation across steps

## Rules

- runtime design first, visual builder later
- graph-aware internals even for sequential MVP
- deterministic context mutation
- explicit cancellation and timeout support
- no hidden cross-step magic

## Progression

1. sequential chains
2. foreach loops and variable propagation
3. conditional execution and retries
4. dependency graph execution
5. visual builder (deferred)

## Key files

- `WORKFLOW_ENGINE.md`
- `FEATURES.md`
- `requirements/functional_requirements.md`
- `docs/subsystems/workflows.md`
