# ADR 0014: Budget `sclpl/notifications` for Batch I

## Decision

Add `sclpl/notifications/` as its own 500-line budget and raise the total
source budget from 26,120 to 26,620 lines.

## Rationale

I4 adds opt-in terminal-run event notifications (webhook, Slack, SMTP) as a
`sclpl.render.reporter.Sink` implementation, self-contained aside from
`notifications -> render` (consuming reporter event types) and
`notifications -> run` (reusing `run/retry.py`'s `Clock` for a testable
backoff). 500 lines covers the delivered config/delivery/sink modules with
modest headroom; it earns its own budget rather than inflating `render` or
`run`, matching the precedent set by `packages` and `importers` for Batches H
and I.
