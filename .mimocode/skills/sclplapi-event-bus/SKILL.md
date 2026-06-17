---
name: sclplapi-event-bus
description: Use when implementing or extending the lightweight in-process event bus for runtime lifecycle, analytics, and diagnostics.
---

## Purpose

Keep the event bus lightweight, in-process, and decoupled from execution logic. Events feed analytics, reports, UI refreshes, and logging without deep coupling.

## When to use

- event publication design
- runtime lifecycle event handling
- analytics feed integration
- diagnostic logging without coupling
- UI refresh triggering from core events

## Rules

- in-process first, no distributed event infrastructure
- lightweight typed payloads
- no business logic hidden inside subscribers
- execution remains correct even if observers fail
- event names must be typed and documented

## Key files

- `docs/subsystems/EVENT_BUS.md`
- `ARCHITECTURE.md`
- `docs/architecture/RUNTIME_MODEL.md`
