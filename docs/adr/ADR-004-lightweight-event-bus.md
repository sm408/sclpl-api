# ADR-004: Lightweight typed internal event bus

## Status

Accepted

## Decision

Use a lightweight in-process event bus for cross-module notifications and extension hooks.

## Rationale

This reduces coupling without dragging the project into heavyweight distributed-systems complexity.

