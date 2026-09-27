"""Rate budgets: requests per time window, per host and per tag (ADR 0017).

`@limits` concurrency caps how many requests are *in flight*; a published API limit
counts how many are *sent* in a window. With fast responses a concurrency of 2 can
still send 30 requests a second, so the two are different promises and need different
machinery.

**A sliding-window log, not a refilling bucket.** A classic token bucket of capacity N
refilling at N/W starts full, so it can spend N at once and then N-1 more as they drip
back in -- up to 2N-1 inside one window. That is exactly the burst a server counting
"3 per second" answers with a 429. Here each budget remembers when its last N requests
were sent, and the next may go only once the oldest of them has left the window. So no
window of length W ever contains more than N sends, which is the promise the spec
makes. Memory is N timestamps per budget.

**All or nothing, in one fixed order.** A request needs a slot from every budget that
applies -- its host's windows, then each tag's in sorted order, the order `_Gate`
acquires semaphores in. It takes them all in one step with no await in between, or
takes none and sleeps until the slowest would allow it. Nothing is ever held while
waiting, so a budget cannot take part in a deadlock at all.

**`Retry-After` closes a host.** A 429 that says when to come back stops every request
to that host until then, not just the one that was told.
"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from sclpl.run.retry import REAL_CLOCK, Clock

#: The window a unit names, in seconds.
UNITS: dict[str, float] = {"s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}

#: Named in every rejection, so a malformed spec says what would have been accepted.
ACCEPTED = (
    "HOST:N/UNIT or tag:NAME:N/UNIT, with N a positive whole number and UNIT one of "
    "s, m, h, d (e.g. api.example.com:3/s, tag:api:120/m)"
)

_RATE = re.compile(r"^([1-9][0-9]*)/([smhd])$")
_NAME = re.compile(r"^[A-Za-z0-9_.\-]+$")


@dataclass(frozen=True, slots=True)
class RateSpec:
    """One parsed `rate=` entry: at most ``count`` requests per ``window`` seconds."""

    key: str
    count: int
    window: float
    text: str


def parse_rate(text: str) -> RateSpec:
    """Read ``api.example.com:3/s`` or ``tag:api:10/s``. Raises ValueError naming the forms."""
    key, _, amount = text.strip().rpartition(":")
    match = _RATE.match(amount)
    name = key[4:] if key.startswith("tag:") else key
    if match is None or not name or not _NAME.match(name):
        raise ValueError(f"rate {text!r} is not a rate budget; expected {ACCEPTED}")
    # Hosts compare case-insensitively, as DNS does; tag names are the author's own.
    key = key if key.startswith("tag:") else key.lower()
    return RateSpec(key, int(match.group(1)), UNITS[match.group(2)], text)


@dataclass(slots=True)
class _Window:
    """When the last ``count`` requests under one spec were sent."""

    spec: RateSpec
    sent: deque[float] = field(default_factory=deque)
    waits: int = 0
    waited_s: float = 0.0

    def ready_in(self, now: float) -> float:
        """Seconds until one more request fits. Drops sends that have left the window."""
        while self.sent and self.sent[0] <= now - self.spec.window:
            self.sent.popleft()
        if len(self.sent) < self.spec.count:
            return 0.0
        return self.sent[0] + self.spec.window - now


class Budgets:
    """Every rate budget for one run, keyed by host or ``tag:NAME``.

    Lives as long as the `Pool` that owns it, so one run's requests share it and a
    caller reusing a pool across runs shares it across them too.
    """

    __slots__ = ("_windows", "_closed", "_clock")

    def __init__(self, specs: Iterable[RateSpec | str] = (), clock: Clock | None = None) -> None:
        self._windows: dict[str, list[_Window]] = {}
        self._closed: dict[str, float] = {}
        self._clock = clock if clock is not None else REAL_CLOCK
        for spec in specs:
            parsed = parse_rate(spec) if isinstance(spec, str) else spec
            self._windows.setdefault(parsed.key, []).append(_Window(parsed))

    def __bool__(self) -> bool:
        return bool(self._windows)

    def _applicable(self, host: str, tags: Iterable[str]) -> list[_Window]:
        """Host first, then tags sorted: the order `_Gate` takes semaphores in."""
        keys = [host.lower(), *(f"tag:{tag}" for tag in sorted(set(tags)))]
        return [window for key in keys for window in self._windows.get(key, [])]

    async def take(self, host: str, tags: Iterable[str] = ()) -> tuple[float, str]:
        """Wait until every applicable budget has room, then spend one slot in each.

        Returns how long it waited and the budget that made it wait longest, for the
        reporter. Nothing is held across the sleep: after waking it checks again.
        """
        applicable = self._applicable(host, tags)
        if not applicable:
            return 0.0, ""
        started = self._clock.now()
        blocker = ""
        while True:
            now = self._clock.now()
            delay, reason = self._closed.get(host.lower(), now) - now, f"{host} Retry-After"
            for window in applicable:
                wait = window.ready_in(now)
                if wait > delay:
                    delay, reason = wait, window.spec.text
            if delay <= 0:
                break
            blocker = blocker or reason
            await self._clock.sleep(delay)
        waited = now - started
        for window in applicable:
            window.sent.append(now)
            if waited > 0:
                window.waits += 1
                window.waited_s += waited
        return waited, blocker

    def close_until(self, host: str, retry_after: float) -> None:
        """A 429 said when to come back: no request to ``host`` goes before then."""
        if host.lower() in self._windows:
            until = self._clock.now() + retry_after
            self._closed[host.lower()] = max(self._closed.get(host.lower(), until), until)

    def stats(self) -> dict[str, Any]:
        """Per spec: its limit, the slots left in the current window, and waiting so far."""
        now = self._clock.now()
        out: dict[str, Any] = {}
        for windows in self._windows.values():
            for window in windows:
                window.ready_in(now)
                out[window.spec.text] = {
                    "limit": window.spec.count,
                    "window_s": window.spec.window,
                    "remaining": window.spec.count - len(window.sent),
                    "waits": window.waits,
                    "waited_s": round(window.waited_s, 3),
                }
        return out


__all__ = ["ACCEPTED", "Budgets", "RateSpec", "UNITS", "parse_rate"]
