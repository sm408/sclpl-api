"""A reporter `Sink` that fans matching events out to configured notifiers.

Delivery is scheduled as a background task from `handle()`, which must never
block the reporter's pump -- `Reporter._dispatch` already isolates one raising
sink from the others, but a *slow* `handle()` would stall every sink's view of
every later event. The run command awaits `wait()` explicitly, once, after the
run's own result is decided and every event up to `RunFinished` has drained
through the reporter -- see `sclpl.render.reporter.Reporter.drain`.
"""

from __future__ import annotations

import asyncio
from typing import Any

from sclpl.notifications.config import NotificationConfig
from sclpl.notifications.delivery import DeliveryReceipt, deliver, idempotency_key
from sclpl.render.events import Event, RunFinished, RunStarted, StepFinished, as_dict

#: How long the run command waits for outstanding deliveries before moving on.
#: Delivery itself already bounds each attempt; this bounds the *sum* across
#: every configured notifier so one very slow endpoint cannot hang the CLI.
DEFAULT_TIMEOUT = 15.0


class NotificationSink:
    def __init__(
        self, configs: tuple[NotificationConfig, ...], *, run_id: str, workflow: str
    ) -> None:
        self._configs = [config for config in configs if config.enabled]
        self._run_id = run_id
        self._workflow = workflow
        self._tasks: list[asyncio.Task[DeliveryReceipt]] = []
        self.receipts: list[DeliveryReceipt] = []

    def handle(self, event: Event) -> None:
        matched = _matching_event_name(event)
        if matched is None or not self._configs:
            return
        payload: dict[str, Any] = {
            "workflow": self._workflow,
            "run_id": self._run_id,
            **as_dict(event),
        }
        for config in self._configs:
            if matched not in config.on:
                continue
            key = idempotency_key(self._run_id, config.name, matched)
            self._tasks.append(asyncio.ensure_future(deliver(config, payload, key=key)))

    def close(self) -> None:
        """A last-resort safety net: `wait()` is the real, awaited shutdown path."""
        for task in self._tasks:
            if not task.done():
                task.cancel()

    async def wait(self, *, timeout: float = DEFAULT_TIMEOUT) -> list[DeliveryReceipt]:
        """Await every scheduled delivery, up to `timeout` in total.

        Must be called (and awaited) from inside the reporter's own event
        loop, after `await reporter.drain()`, and before the `async with
        reporter:` block exits -- `Sink.close()` is synchronous and cannot
        safely await anything itself.
        """
        if not self._tasks:
            return []
        done, pending = await asyncio.wait(self._tasks, timeout=timeout)
        for task in pending:
            task.cancel()
        self.receipts = [task.result() for task in done]
        if pending:
            self.receipts.extend(
                DeliveryReceipt("(unknown)", "failed", 0, "timed out waiting for delivery")
                for _ in pending
            )
        return self.receipts


def _matching_event_name(event: Event) -> str | None:
    if isinstance(event, RunStarted):
        return "run_started"
    if isinstance(event, RunFinished):
        return "run_finished"
    if isinstance(event, StepFinished) and event.status == "failed":
        return "step_failed"
    return None
