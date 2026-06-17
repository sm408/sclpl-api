---
name: sclplapi-core-architecture
description: Use when planning or implementing core architecture, layering, contracts, or subsystem boundaries for SCLPLAPI.
---

## Purpose

Keep SCLPLAPI aligned with the local-first, Python-first platform doctrine. Enforce `ui -> services -> core -> storage` layer direction. Prevent hidden coupling and premature platform sprawl.

## When to use

- architecture planning or review
- module placement decisions
- subsystem ownership questions
- contract boundary design
- reviewing whether a change belongs in core, services, UI, or storage

## Rules

- layer direction is `ui -> services -> core -> storage` — never reversed
- core must remain UI-independent
- typed, explicit execution context over hidden globals
- prefer graph-capable internals even when visible UI is sequential
- strict core, flexible feature layer

## Key files

- `AGENTS.md`
- `ARCHITECTURE.md`
- `FEATURES.md`
- `CODING_STANDARDS.md`
- `rules/architecture-rules.md`
- `docs/architecture/API_CONTRACTS.md`
- `docs/architecture/RUNTIME_MODEL.md`
