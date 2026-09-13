"""I4: opt-in terminal-run event notifications -- webhook, Slack, and SMTP.

Delivery is best effort: a `DeliveryReceipt` records what happened, but nothing
here retries across process restarts. Durable post-process delivery needs the
deferred operations layer this batch does not build. A notifier failing never
rewrites the workflow's own exit code -- `sclpl.render.reporter.Reporter`
already isolates a raising sink, and sending itself happens after the run's
own result is already decided.
"""

from __future__ import annotations
