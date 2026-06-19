# ADR-006: Parallel workflow engine

## Status

Accepted

## Decision

Build a parallel workflow engine alongside the sequential one.

## Rationale

Independent API calls should execute concurrently. A dependency-graph-based engine with `asyncio.create_task` provides automatic parallelization while the sequential engine remains for simple chains.
