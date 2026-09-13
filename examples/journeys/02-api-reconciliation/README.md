# Journey 2 — API reconciliation

Reconciles orders from an API against a local accounting ledger and produces
a stable discrepancy report with lineage (where each row's numbers came
from). Journey 2 of `docs/cli-rebuild/UNIFIED-UPGRADE-PLAN.md` section 7.

## Layout

- `workflows/reconciliation.sclpll` — fetch, validate, reconcile, export.
- `reconcile.py` — a registered, hash-pinned Python script (see
  `[python.scripts.reconcile]` in `sclpl.toml`) that joins the two sides by
  `id` and labels each row `matched`, `mismatch`, `api_only`, or
  `ledger_only`.
- `fixtures/api/` — a recorded offline HTTP fixture for `GET {{base}}/orders`.
- `fixtures/ledger.csv` — the accounting ledger, as a plain local CSV.
- `fixtures/ledger_duplicate.csv` — the same ledger with a duplicated `id`.
  Used for the required negative case below.

## Running it

```
sclpl run workflows/reconciliation.sclpll \
  --var base=http://127.0.0.1:PORT \
  --out report=report.json \
  --replay fixtures/api --strict-replay --no-record --no-cache
```

Entirely offline: `--replay` serves the API side, and the ledger is a
checked-in file read straight off disk.

## Passing result

Both sides are checked with `assert_unique @x "id"` before anything else
happens. `reconcile.py` then labels every id present on either side, so the
report has full lineage instead of only surfacing what already agreed.

## Required negative case

Point `--var ledger_path=fixtures/ledger_duplicate.csv` at the corrupted
ledger: it has two rows for `id` 2. `ledger_checked` fails with
`id is not unique: 2` (exit code 4) before the API side is even touched — a
duplicate join key can never silently produce a report.

See `tests/integration/test_journeys.py` for the automated version of both
cases.
