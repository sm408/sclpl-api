"""Secret redaction.

Invariant 9: secrets never reach a log, a bar label, or a trace dump. Redaction lives
here, in the reporter, rather than at each call site — a call site that forgets is a
leak, and there is no way to audit for the omission. Every event crosses this filter
before any sink sees it, so a new sink cannot introduce a leak either.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from typing import Any

from sclpl.render.events import Event

MASK = "[redacted]"

#: Values shorter than this are not substituted. A two-character secret would match
#: inside ordinary words and shred every message, which is its own kind of failure.
#: Secrets this short are rejected at registration instead (see `Redactor.add`).
MIN_LENGTH = 4


class TooShortToRedact(ValueError):
    """Raised when a secret is too short to be substituted safely."""


class Redactor:
    """Substitutes known secret values out of outbound events."""

    __slots__ = ("_values",)

    def __init__(self, secrets: Iterable[str] = ()) -> None:
        self._values: list[str] = []
        for secret in secrets:
            self.add(secret)

    def add(self, value: str) -> None:
        if not value:
            return
        if len(value) < MIN_LENGTH:
            raise TooShortToRedact(
                f"refusing to register a {len(value)}-character secret: it would match "
                f"inside ordinary text. Secrets must be at least {MIN_LENGTH} characters."
            )
        if value not in self._values:
            self._values.append(value)
        # Longest first, so an API key that contains a shorter one is masked whole.
        self._values.sort(key=len, reverse=True)

    def __bool__(self) -> bool:
        return bool(self._values)

    def scrub(self, text: str) -> str:
        for value in self._values:
            if value in text:
                text = text.replace(value, MASK)
        return text

    def apply(self, event: Event) -> Event:
        """Return ``event`` with every string reachable in it scrubbed."""
        if not self._values:
            return event
        changes: dict[str, Any] = {}
        for name in type(event).__dataclass_fields__:
            original = getattr(event, name)
            scrubbed = self._scrub_value(original)
            if scrubbed is not original:
                changes[name] = scrubbed
        if not changes:
            return event
        return dataclasses.replace(event, **changes)

    def _scrub_value(self, value: Any) -> Any:
        if isinstance(value, str):
            cleaned = self.scrub(value)
            return value if cleaned == value else cleaned
        if isinstance(value, tuple):
            items = tuple(self._scrub_value(item) for item in value)
            return value if items == value else items
        if isinstance(value, list):
            items_list = [self._scrub_value(item) for item in value]
            return value if items_list == value else items_list
        if isinstance(value, dict):
            mapping = {key: self._scrub_value(item) for key, item in value.items()}
            return value if mapping == value else mapping
        return value
