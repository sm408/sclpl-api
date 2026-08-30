# `tables/`

Budget 900. Tabular data and the formats it lives in.

| File | Job |
|---|---|
| `base.py` | `Table`, `TableBackend` protocol, `MissingExtra`, `as_table` |
| `pandas_backend.py` | The only file that imports pandas, and lazily |
| `flatten.py` | The §10 reference semantics; `records_of`; `infer_schema` |
| `io.py` | Format dispatch: read, write, and `-` for stdout |

→ [[Tables and Flattening]]

## `Table` is a wrapper, not a subclass

`content_digest()` follows content, not identity — which is what the M7 cache key will
depend on. `to_parquet()` is found by name by the spill path.
