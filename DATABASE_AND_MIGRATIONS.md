# DATABASE_AND_MIGRATIONS.md

## Storage doctrine

SQLite is the default and first-class persistence backend.

## Why SQLite first

- local-first
- easy setup
- portable
- inspectable
- sufficient for the first single-user phases

## Persisted domains

- collections
- requests
- environments
- history
- workflow definitions
- plugin configuration
- export presets

## Migration rules

- all schema changes must be versioned
- user data must be migratable
- refactors must not silently invalidate saved workspaces

## Future direction

Additional storage backends may become possible later, but architecture should not optimize for PostgreSQL-first complexity at the current stage.

