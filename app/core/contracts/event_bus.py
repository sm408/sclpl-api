from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Event:
    name: str
    data: dict[str, Any] = field(default_factory=dict)
    source: str = ""


EventHandler = Callable[[Event], None]


class EventBus(ABC):
    @abstractmethod
    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        ...

    @abstractmethod
    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        ...

    @abstractmethod
    def publish(self, event: Event) -> None:
        ...
