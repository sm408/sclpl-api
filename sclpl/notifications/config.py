"""`[notifications.<name>]` project manifest tables, parsed and validated."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sclpl.errors import ValidationError

KINDS = frozenset({"webhook", "slack", "smtp"})
EVENTS = frozenset({"run_started", "run_finished", "step_failed"})
DEFAULT_EVENTS = frozenset({"run_finished"})


@dataclass(frozen=True, slots=True)
class NotificationConfig:
    name: str
    kind: str
    enabled: bool
    on: frozenset[str]
    url: str | None = None
    to: tuple[str, ...] = ()
    from_address: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587


def parse(manifest: dict[str, Any], *, where: str) -> tuple[NotificationConfig, ...]:
    """Parse every `[notifications.<name>]` table. Raises on a malformed one."""
    raw = manifest.get("notifications", {})
    if not isinstance(raw, dict):
        raise ValidationError("notifications must be a table", where=where)

    configs: list[NotificationConfig] = []
    for name, table in raw.items():
        if not isinstance(table, dict):
            raise ValidationError(f"notifications.{name} must be a table", where=where)
        configs.append(_parse_one(name, table, where))
    return tuple(configs)


def _parse_one(name: str, table: dict[str, Any], where: str) -> NotificationConfig:
    kind = table.get("kind")
    if kind not in KINDS:
        raise ValidationError(
            f"notifications.{name}.kind must be one of {sorted(KINDS)}", where=where
        )
    enabled = bool(table.get("enabled", False))
    on_raw = table.get("on", sorted(DEFAULT_EVENTS))
    if not isinstance(on_raw, list) or not all(isinstance(item, str) for item in on_raw):
        raise ValidationError(f"notifications.{name}.on must be an array of strings", where=where)
    on = frozenset(on_raw)
    unknown = on - EVENTS
    if unknown:
        raise ValidationError(
            f"notifications.{name}.on has unknown event {sorted(unknown)[0]!r}; "
            f"expected one of {sorted(EVENTS)}",
            where=where,
        )

    if kind in ("webhook", "slack"):
        url = table.get("url")
        if not isinstance(url, str) or not url:
            raise ValidationError(f"notifications.{name}.url is required", where=where)
        return NotificationConfig(name, kind, enabled, on, url=url)

    to = table.get("to")
    from_address = table.get("from")
    smtp_host = table.get("smtp_host")
    if (
        not isinstance(to, list)
        or not to
        or not all(isinstance(item, str) for item in to)
        or not isinstance(from_address, str)
        or not isinstance(smtp_host, str)
    ):
        raise ValidationError(
            f"notifications.{name} needs a non-empty 'to' array, 'from', and 'smtp_host'",
            where=where,
        )
    smtp_port = table.get("smtp_port", 587)
    if not isinstance(smtp_port, int):
        raise ValidationError(f"notifications.{name}.smtp_port must be an integer", where=where)
    return NotificationConfig(
        name,
        kind,
        enabled,
        on,
        to=tuple(to),
        from_address=from_address,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
    )
