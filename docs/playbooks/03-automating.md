# Running it every night

What changes when a person is not watching.

## Use `run`, not the shorthand

```bash
sclpl run orders.sclpll --mode nightly out.csv
```

The bare form (`sclpl orders nightly out.csv`) is for typing. Scripts and CI use `run`,
because the shorthand's meaning depends on what is in your catalogue and a script should
not.

## Exit codes are the interface

| Code | Means | React by |
|---:|---|---|
| 0 | fine | — |
| 1 | a step failed | retrying may help |
| 2 | the command line was wrong | fixing the script |
| 3 | preflight refused it | fixing the workflow; **nothing ran** |
| 4 | an assertion failed | looking at the **data** |
| 5 | `--offline` and a cache miss | running once online |
| 6 | no such workflow | checking the name |

3 and 4 are the two that earn their keep. 3 means nothing happened, so re-running after
a fix costs nothing. 4 means the requests succeeded and the answers were wrong.

## Machine-readable output

```bash
sclpl --json run orders.sclpll out.csv 2> events.ndjson
```

NDJSON on **stderr**, because stdout is data. Every event: each step starting and
finishing, each retry, each page, each value freed.

## A mode for the schedule

```
@mode nightly "Everything, no page cap"
  extends full

@mode smoke "One page, no writes"
  include fetch
  limit max_pages=1
```

A mode can only **subtract** steps and override scalars. Pruning something a kept step
needs fails at `validate` time with the fix named — so a broken mode is caught by CI
rather than at 3am.

## Secrets in CI

There is no keyring on a build agent, so:

```bash
export SCLPL_SECRET_API_TOKEN="$TOKEN_FROM_YOUR_CI"
sclpl run orders.sclpll out.csv
```

`sclpl` reads that variable; it never *writes* one. Where a secret is stored and where it
is read from are different questions, and the refusal to store weakly does not stop it
reading what CI already provides.

## Keep the history

```bash
sclpl run orders.sclpll out.csv --tag nightly --name "orders-$(date +%F)"
sclpl runs list --workflow orders
sclpl runs search "timed out"
```

Retention is 5 by default. `sclpl runs pin <id>` keeps one indefinitely, and a pinned run
does not count against the limit.

Each run also writes a self-contained NDJSON log, so history is greppable without
touching the database.

## Being polite to the remote

```
@limits concurrency=8 host_concurrency=4 timeout=20
```

Every one of those is a promise to somebody else's server. Adaptive concurrency lowers
them further on 429 and 503, honouring `Retry-After` exactly. It never raises them above
what you set.

## What to read next

- Something failed and you need to know why → [Debugging](04-debugging.md)
