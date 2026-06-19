# ADR-007: SCLPLL scripting language

## Status

Accepted

## Decision

Create a domain-specific language for workflow definitions.

## Rationale

Raw `workflow.json` is verbose and error-prone. A human-readable DSL with compile/decompile enables faster authoring while maintaining backward compatibility with JSON.
