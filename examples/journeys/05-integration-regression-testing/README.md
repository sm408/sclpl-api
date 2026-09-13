# Journey 5 — Integration regression testing

Packages a workflow that exercises authentication, retry, and cursor
pagination together, installs it somewhere else, and replays it there fully
offline. Journey 5 of `docs/cli-rebuild/UNIFIED-UPGRADE-PLAN.md` section 7.

## Layout

- `workflows/regression.sclpll` — an authenticated (`secret('demo_token')`),
  retrying (`retry 3 on=[503]`), paginated (`paginate cursor ...`) fetch.
- `sclpl.toml` — `[package]` names and versions this project so `sclpl
  package build` can bundle it.
- `fixtures/orders/` — a recorded fixture that captures the *whole*
  sequence: page one's first attempt (503), its retry (200), and page two.
  Replaying it reproduces the retry and the pagination exactly, with no
  live server involved.

## Running it

```
sclpl package build --out dist/pkg.sclplpkg
sclpl package install dist/pkg.sclplpkg --into deployed

cd deployed/integration-regression-testing/1.0.0
SCLPL_SECRET_DEMO_TOKEN=secret-token-xyz sclpl run workflows/regression.sclpll \
  --var base=http://127.0.0.1:PORT \
  --out rows=rows.csv \
  --replay fixtures/orders --strict-replay --no-record --no-cache
```

The secret is never stored in the fixture or the package -- `secret()` reads
`SCLPL_SECRET_DEMO_TOKEN` at run time, in the installed copy exactly as it
would in the original project (SPEC: "auth references", never a literal
credential).

## Passing result

`fixtures/orders` is bundled into the package automatically (conventional
`fixtures/` directory, `sclpl/packages/build.py`). Once installed, the same
fixture replays the same three-request sequence -- unauthorized-free,
retried, paginated -- with nothing live involved, and `rows.csv` gets all
three records across both pages.

## Required negative case

Rename the installed copy's `fixtures/orders` directory away and rerun: the
first request has nothing to replay against, so `fetch` fails immediately
with `fixture mismatch` (exit code 3) -- before pagination, before
`shape`, before `write` ever runs. No `rows.csv` appears. A missing fixture
can never produce a plausible-looking but wrong regression result.

See `tests/integration/test_journeys.py` for the automated version of both
cases, including the real `package build` / `package install` round trip.
