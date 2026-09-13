# Journey 1 — API-to-CSV reporting

Fetches orders from an API, validates their shape, and publishes a CSV report.
This is the first of the five business-acceptance journeys in
`docs/cli-rebuild/UNIFIED-UPGRADE-PLAN.md` section 7.

## Layout

- `workflows/orders_report.sclpll` — fetch, validate, export.
- `fixtures/orders/` — a recorded offline HTTP fixture: two orders, both complete.
- `fixtures/orders_missing_field/` — the same shape, but the second order is
  missing `total`. Used for the required negative case below.

## Running it

```
sclpl run workflows/orders_report.sclpll \
  --var base=http://127.0.0.1:PORT \
  --out report=report.csv \
  --replay fixtures/orders --strict-replay --no-record --no-cache
```

No network access or live server is needed — `--replay` serves the recorded
fixture. `--var base=...` only has to match the URL the fixture was recorded
against; nothing outside `fixtures/orders` is contacted.

## Passing result

`fetch_orders` gets `{{base}}/orders` and asserts a 200. `validated` checks the
response against a schema (`id`, `customer`, `total`) and rejects any row with a
null in `total`. `write_report` flattens the validated rows into `report.csv`.

## Required negative case

Point `--replay` at `fixtures/orders_missing_field` instead: the second order
is missing `total`. `validated` fails with `null values in: total (1)` (exit
code 4) before `write_report` ever runs — no CSV is written, so a required
field silently disappearing can never produce a report someone could
mistake for trustworthy.

See `tests/integration/test_journeys.py` for the automated version of both
cases.
