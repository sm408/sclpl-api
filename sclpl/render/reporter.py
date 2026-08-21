"""The reporter facade: one queue in, one writer out.

Invariant 4 in one place. Every worker, plugin, and log record calls `Reporter.emit`,
which only ever appends to a queue. Exactly one task — the pump started by
`Reporter.__aenter__` — drains that queue and touches the stderr handle. That is what
keeps a live region intact while a worker pool runs underneath it.

Redaction happens here too (invariant 9), on the way out of the queue and before any
sink sees an event, so a sink cannot leak a secret its author never thought about.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from collections.abc import Sequence
from types import TracebackType
from typing import Protocol, TextIO, runtime_checkable

from sclpl.render.events import Event, Level, LogRecord
from sclpl.render.human import HumanSink
from sclpl.render.jsonl import JsonlSink
from sclpl.render.plain import PlainSink, QuietSink
from sclpl.render.redact import Redactor
from sclpl.render.term import Caps, TerminalGuard, probe


@runtime_checkable
class Sink(Protocol):
    """Anything that can present an event. Structural — sinks import nothing from here."""

    def handle(self, event: Event) -> None: ...

    def close(self) -> None: ...


class _Sentinel:
    __slots__ = ()


_STOP = _Sentinel()


class Reporter:
    """Fan-out to every configured sink, through a single writer task."""

    __slots__ = ("_sinks", "_redactor", "_queue", "_pump", "_guard", "_closed")

    def __init__(
        self,
        sinks: Sequence[Sink],
        *,
        redactor: Redactor | None = None,
        guard: TerminalGuard | None = None,
    ) -> None:
        self._sinks: list[Sink] = list(sinks)
        self._redactor = redactor if redactor is not None else Redactor()
        self._queue: asyncio.Queue[Event | _Sentinel] = asyncio.Queue()
        self._pump: asyncio.Task[None] | None = None
        self._guard = guard
        self._closed = False

    # -- producer side -----------------------------------------------------------

    def emit(self, event: Event) -> None:
        """Enqueue an event. Never blocks, never writes, safe from any worker."""
        if self._closed:
            return
        self._queue.put_nowait(event)

    def log(self, level: Level, message: str, step: str | None = None) -> None:
        self.emit(LogRecord(level=level, message=message, step=step))

    def secret(self, value: str) -> None:
        """Register a resolved secret so every later event is scrubbed of it."""
        self._redactor.add(value)

    # -- lifecycle ---------------------------------------------------------------

    async def __aenter__(self) -> Reporter:
        if self._guard is not None:
            self._guard.arm()
        self._pump = asyncio.create_task(self._run_pump(), name="sclpl-reporter")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def drain(self) -> None:
        """Wait until everything queued so far has been presented."""
        await self._queue.join()

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._queue.put_nowait(_STOP)
        if self._pump is not None:
            await self._pump
            self._pump = None
        for sink in self._sinks:
            # Closing must not mask the error that is already on its way out.
            with contextlib.suppress(Exception):
                sink.close()
        if self._guard is not None:
            self._guard.restore()

    # -- consumer side -----------------------------------------------------------

    async def _run_pump(self) -> None:
        while True:
            item = await self._queue.get()
            try:
                if isinstance(item, _Sentinel):
                    return
                self._dispatch(self._redactor.apply(item))
            finally:
                self._queue.task_done()

    def _dispatch(self, event: Event) -> None:
        for sink in list(self._sinks):
            try:
                sink.handle(event)
            except Exception:  # noqa: BLE001 - a broken terminal must not fail the run
                self._descend(sink)

    def _descend(self, sink: Sink) -> None:
        """A sink that raised drops one rung, or out (invariant 5: never back up)."""
        index = self._sinks.index(sink)
        lower = getattr(sink, "descend", None)
        if callable(lower):
            try:
                self._sinks[index] = lower()
                return
            except Exception:  # noqa: BLE001
                pass
        del self._sinks[index]


def build_reporter(
    *,
    verbosity: int = 0,
    json_mode: bool = False,
    plain: bool = False,
    no_color: bool = False,
    stream: TextIO | None = None,
    caps: Caps | None = None,
) -> Reporter:
    """Choose the sink for this invocation and wire it up.

    Precedence, highest first: `--json` (machine output wins over everything human),
    `-qq`/`-q`, then the probed rung with `--plain` and `--no-color` able to lower it.
    Nothing here can raise the rung above what the probe allowed.
    """
    stream = stream if stream is not None else sys.stderr
    caps = caps if caps is not None else probe(stream)
    if plain:
        while caps.rung != "plain":
            caps = caps.descend()
    if no_color:
        caps = Caps(
            rung=caps.rung,
            color=False,
            unicode=caps.unicode,
            width=caps.width,
            height=caps.height,
        )

    sinks: list[Sink]
    guard: TerminalGuard | None = None
    if json_mode:
        sinks = [JsonlSink(stream)]
    elif verbosity <= -2:
        sinks = [QuietSink(stream, silent=True)]
    elif verbosity == -1:
        sinks = [QuietSink(stream)]
    elif caps.rung == "plain":
        sinks = [PlainSink(stream, verbosity)]
    else:
        sinks = [HumanSink(caps, stream, verbosity)]
        guard = TerminalGuard(caps, stream)
    return Reporter(sinks, guard=guard)


__all__ = ["Reporter", "Sink", "build_reporter"]
