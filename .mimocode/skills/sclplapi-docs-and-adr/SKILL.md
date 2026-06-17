---
name: sclplapi-docs-and-adr
description: Use when updating source-of-truth docs, subsystem guides, ADRs, or roadmap material for SCLPLAPI.
---

## Purpose

Keep documentation honest, implementation-guiding, and architecture-aligned. Route meaningful decisions into ADRs. Prevent roadmap, feature, and architecture docs from diverging.

## When to use

- source-of-truth doc updates
- ADR creation or updates
- requirement document changes
- contributor guidance changes
- roadmap or planning doc updates

## Rules

- never blur planned work with implemented work
- update source-of-truth docs when contracts or subsystem boundaries move
- add ADRs for decisions that would otherwise be rediscovered
- prefer concise, technical, implementation-guiding prose

## Key files

- `AGENTS.md`
- `docs/decisions/DECISIONS.md`
- `docs/adr/`
- `rules/documentation-rules.md`
- `CONTRIBUTING.md`
- `CHANGELOG.md`
