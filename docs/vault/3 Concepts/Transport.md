---
tags:
  - concept
---

# Transport

`run/transport.py`. Pooled `httpx` clients, per-host breakers, adaptive limits.

## One client per profile, not per request

[[Why a Rewrite|Defect 3]] was a new `AsyncClient` — and therefore a new TCP connection,
and a new TLS handshake — for every request. Clients are keyed by
`(scheme, host, port, auth mode, proxy, verify)` and owned by the run.

`aclose` is idempotent and closes every client even if one raises: a leaked connection
outlives the process that made it, in the sense that the remote keeps it open waiting.

## HTTP/2

Probed, not assumed. `HTTP2_AVAILABLE` checks whether `h2` is importable; without it,
asking for HTTP/2 would be a hard crash at the first request rather than a fallback.
`httpx[http2]` is the declared dependency.

## A non-2xx is not an exception

An API that answers 404 has answered. The status is part of the result, and `assert
@fetch.status == 200` is how a workflow says it cares. Raising instead would make the
common "check for 404, take the other branch" shape impossible to write.

## Retries

`run/retry.py`. Exponential backoff with jitter, honouring `Retry-After` exactly when
the server sends one. `retry_if` on a step decides whether a particular failure is worth
retrying.

## Adaptive concurrency

AIMD per host (`Adaptive` in `run/retry.py`): a 429 or 503 halves the host's limit, and
it climbs back one step per window of responses (32) while p95 latency stays flat.
The pool measures; the scheduler admits. `Pool.follow_limits` hands each change to
`Scheduler.limit_host`, which resizes that host's slot in the ordered gate. Requests
already in flight finish normally; only new admissions wait for the lower limit, the
same contract as memory-pressure throttling.

It never exceeds the static per-host cap (`--host-concurrency`, `limits.host_concurrency`)
and never goes below one. Each change is a `host_limit_changed` event (host, previous,
limit, ceiling, reason), shown at the default verbosity and recorded in the NDJSON run
log, so a run that slowed down says why. A step whose URL host is only known after
interpolation has no host bucket and is governed by the global ceiling alone.

There is no CLI switch to turn adaptation off; embedders pass `Pool(adaptive=False)`.

## Rate budgets

`run/rate.py`, [ADR 0017](../../adr/0017-rate-budgets.md). `@limits rate=HOST:N/UNIT` and
`rate=tag:NAME:N/UNIT` count *requests sent*, where concurrency counts requests in flight.
Every attempt takes a slot, retries and pages included, just before it is sent.

A sliding-window log rather than a refilling bucket: a bucket of N can spend 2N-1 in one
window, the log never more than N. Slots are taken from every applicable budget at once, in
the same host-then-sorted-tags order as the scheduler's semaphores, or not at all -- nothing
is held while waiting, so there is nothing to deadlock on. A 429 with `Retry-After` closes a
budgeted host until then. `Pool.stats()["rates"]` and the `step_throttled` event show what
was left and what was waited.

## Decoding

`decode()` turns a body into a typed value. → [[Typed Values]]
