# `catalog/`

Budget 500. Named workflows on disk.

| File | Job |
|---|---|
| `store.py` | Where registered workflows live; versioning by content hash |
| `resolve.py` | Name → path, with the resolution order |

A bare name is looked up here; a path is used as-is. A misspelled name produces a
suggestion and exit **6** (`EXIT_UNKNOWN_TARGET`), not a "file not found".

Versioning is by content hash, so importing the same file twice is idempotent and
importing a changed file is a new version rather than a silent overwrite.
