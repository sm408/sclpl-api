from __future__ import annotations

import logging
from collections import defaultdict

from app.core.contracts.event_bus import Event, EventBus, EventHandler

logger = logging.getLogger(__name__)


class SimpleEventBus(EventBus):
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._handlers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        handlers = self._handlers.get(event_name, [])
        if handler in handlers:
            handlers.remove(handler)

    def publish(self, event: Event) -> None:
        for handler in self._handlers.get(event.name, []):
            try:
                handler(event)
            except Exception:
                logger.exception("Event handler error for %s", event.name)

        for handler in self._handlers.get("*", []):
            try:
                handler(event)
            except Exception:
                logger.exception("Wildcard event handler error for %s", event.name)
