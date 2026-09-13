# Journey 4 — Lightweight ingestion

Ingests typed records into a Parquet dataset, but only ever publishes it if
the whole run succeeds. Journey 4 of
`docs/cli-rebuild/UNIFIED-UPGRADE-PLAN.md` section 7.

## Layout

- `workflows/ingest.sclpll` — fetch, type, write, then gate on row count.
- `sclpl.toml` — `[outputs] publish = "validated"` (SPEC 3.5,
  `sclpl/run/publication.py`): every declared output writes to a scratch
  file first, and none of them replace their real destination unless every
  step in the run finished without a single failure.
- `fixtures/records_full/` — three records (passes the row-count gate).
- `fixtures/records_incomplete/` — only two records. Used for the required
  negative case below.

## Running it

```
sclpl run workflows/ingest.sclpll \
  --var base=http://127.0.0.1:PORT \
  --out dataset=dataset.parquet \
  --replay fixtures/records_full --strict-replay --no-record --no-cache
```

## Passing result

`quality_gate` (`assert_rowcount(@typed, min=3)`) runs after `write`. Because
it passes, the run finishes clean and the CLI logs `published: dataset` --
the scratch file replaces `dataset.parquet` in one atomic rename.

## Required negative case

Point `--replay` at `fixtures/records_incomplete`: the source only has two
records. `write` still runs and produces a value (writer steps are not
gated on later steps -- there is no dependency between them a graph could
see), but `quality_gate` then fails, so the *run* fails. The CLI logs
`run did not succeed; discarded staged output(s): dataset`, and
`dataset.parquet` is left exactly as it was before this run -- if a prior
successful run had already published three rows there, they are still all
three rows afterward. An interrupted or invalid ingestion can never be
mistaken for a completed dataset, whether it fails on the first run (no
file appears) or the tenth (the file from run nine is untouched).

See `tests/integration/test_journeys.py` for the automated version of both
cases, including the "a bad run must not clobber a previously good file"
check.
