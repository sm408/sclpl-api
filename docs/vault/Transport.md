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

AIMD per host: additive increase while p95 is flat, multiplicative decrease on 429/503.
It never exceeds the static caps — `--no-adaptive` pins it. Every admission decision is
logged at `-vvv`.

## Decoding

`decode()` turns a body into a typed value. → [[Typed Values]]
