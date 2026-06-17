# Event Bus

SCLPLAPI uses a lightweight internal event bus to decouple runtime reporting from execution logic.

## Purpose

- publish execution lifecycle events
- feed analytics and reports
- drive non-critical UI refreshes
- support logging and diagnostics without deep coupling

## Principles

- in-process first
- lightweight payloads
- typed event names
- no business logic hidden inside subscribers
- execution remains correct even if observers fail

## Event families

- request started/completed/failed
- workflow started/node-completed/failed/finished
- function started/completed/failed
- export started/completed/failed

## Guardrails

- the event bus is observational, not the source of truth
- subscribers must not mutate core runtime state directly
- high-volume event streams must remain bounded and cheap

Primary references:

- `RUNTIME_MODEL.md`
- `WORKFLOW_ENGINE.md`
- `ANALYTICS_ENGINE.md`
