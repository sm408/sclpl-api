# Storage Model

The storage model defines how SCLPLAPI persists workspace state, runtime records, and generated artifacts.

## Storage domains

- project metadata
- requests and collections
- environments and variables
- workflow definitions
- run history
- export metadata

## Principles

- storage stays behind services and repositories
- schema changes are migration-driven
- runtime records and authored definitions remain distinguishable
- local file compatibility matters for inspection and backup

Primary references:

- `DATABASE_AND_MIGRATIONS.md`
- `DATABASE.md`
