# ADR-008: Dot notation for variable access

## Status

Accepted

## Decision

Support `{{step_id.field.subfield}}` syntax for nested JSON access.

## Rationale

API responses are deeply nested. Dot notation provides direct access without extraction functions, with graceful fallback on missing keys.
