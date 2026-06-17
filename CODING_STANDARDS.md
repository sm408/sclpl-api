# CODING_STANDARDS.md

## Core rule

Strict in the core, flexible in the feature layer.

## Mandatory standards

- typed core contracts
- async discipline
- explicit architecture boundaries
- ruff formatting/lint compatibility
- black formatting compatibility
- pytest for automated validation

## Modeling rule

- dataclasses for internal execution/runtime models
- Pydantic for external or untrusted data boundaries

## Async rule

- no blocking network calls in async flows
- background tasks must be cancellable
- request and workflow execution paths need timeout support

## File size rule

- soft limit: 500-700 LOC
- treat 1000+ LOC files as architectural warnings

## Anti-patterns

- god files
- circular imports
- hidden globals
- UI-driven business logic
- duplicated variable-resolution code
- plugin reliance on undocumented internals

