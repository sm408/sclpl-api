# Journey 3 — API quality monitoring

Checks the orders API against a schema on every run and raises a notification
the moment it breaks. Journey 3 of
`docs/cli-rebuild/UNIFIED-UPGRADE-PLAN.md` section 7.

## Layout

- `workflows/quality_check.sclpll` — fetch, contract-check, summarize.
- `sclpl.toml` — `[notifications.quality_alert]`: a webhook fired on
  `step_failed`, pointed at `http://127.0.0.1:8903/notify`.
- `fixtures/orders_ok/` — a recorded fixture matching the expected schema.
- `fixtures/orders_breaking/` — the same shape, but `total` was renamed to
  `amount`. Used for the required negative case below.

## Running it

```
sclpl run workflows/quality_check.sclpll \
  --var base=http://127.0.0.1:PORT \
  --out report=report.json \
  --replay fixtures/orders_ok --strict-replay --no-record --no-cache
```

## Passing result

`contract_check` runs `assert_schema` against `id`/`customer`/`total`. Nothing
in `[notifications.quality_alert].on` matches a passing run, so it stays
quiet and `write_report` publishes a summary.

## Required negative case

Point `--replay` at `fixtures/orders_breaking` instead: the API renamed
`total` to `amount`, so `total` is entirely missing from the response.
`contract_check` fails with `missing column: total` (exit code 4), and the
webhook fires a `step_failed` event.

That notification is delivered best-effort and never changes the run's own
result (SPEC 7: *"delivery failure is separately recorded"*) — whether a
receiver is listening or not, the run still exits 4. The CLI logs which
happened either way:

```
info: notification quality_alert: delivered in 1 attempt(s)
```
or, with nothing listening on 8903:
```
warning: notification quality_alert: failed in 3 attempt(s): ...
```

See `tests/integration/test_journeys.py` for the automated version of all
three cases, and `tests/integration/test_notifications_cli.py` for the
underlying delivery-logging mechanism in isolation.
