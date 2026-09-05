"""Safe command-line persistence for history and replay suggestions."""

from __future__ import annotations

from collections.abc import Iterable

_SENSITIVE = (
    "secret",
    "token",
    "password",
    "passwd",
    "api-key",
    "api_key",
    "apikey",
    "authorization",
)
REDACTED = "[redacted]"


def render(argv: Iterable[str]) -> str:
    """Return a replayable command summary without literal credential values."""
    values = list(argv)
    safe: list[str] = []
    redact_next = False
    for value in values:
        lower = value.lower()
        if redact_next:
            safe.append(REDACTED)
            redact_next = False
            continue
        if lower.startswith("--") and "=" not in value and _sensitive(lower):
            safe.append(value)
            redact_next = True
            continue
        name, separator, content = value.partition("=")
        if separator and _sensitive(name.lower()):
            safe.append(f"{name}={REDACTED}")
        else:
            safe.append(value)
    return " ".join(safe)


def _sensitive(value: str) -> bool:
    return any(marker in value for marker in _SENSITIVE)
