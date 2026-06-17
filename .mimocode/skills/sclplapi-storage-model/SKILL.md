---
name: sclplapi-storage-model
description: Use when planning SQLite schemas, persistence ownership, migrations, and data portability for SCLPLAPI.
---

## Purpose

Keep persistence SQLite-first and migration-aware. Clarify which entities belong in durable storage. Protect portability and inspectability.

## When to use

- schema design
- migration planning and versioning
- history persistence
- collection/request storage
- environment storage
- workflow definition persistence
- plugin configuration storage

## Rules

- SQLite is the default and first-class backend
- all schema changes must be versioned
- user data must be migratable
- refactors must not silently invalidate saved workspaces
- storage stays behind services and repositories
- runtime records and authored definitions remain distinguishable

## Key files

- `DATABASE_AND_MIGRATIONS.md`
- `docs/architecture/STORAGE_MODEL.md`
- `docs/architecture/storage.md`
- `requirements/non_functional_requirements.md`
