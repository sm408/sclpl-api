"""The NDJSON sink — ``--json``, and the per-run event log.

One JSON object per line on stderr, because stdout is data (invariant 1). The same
writer backs the run log that `sclpl runs` reads, which is what makes history greppable
without opening the database.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any, TextIO

from sclpl.render.events import Event, as_dict, event_name, visible_at


class JsonlSink:
    """Serialises every event as one NDJSON record.

    Unlike the human sinks this defaults to recording everything: a machine reader can
    filter, and a log that dropped the retry it needed cannot be re-run.
    """

    __slots__ = ("_stream", "_verbosity", "_close_stream")

    def __init__(
        self,
        stream: TextIO | None = None,
        verbosity: int = 3,
        *,
        close_stream: bool = False,
    ) -> None:
        self._stream = stream if stream is not None else sys.stderr
        self._verbosity = verbosity
        self._close_stream = close_stream

    def handle(self, event: Event) -> None:
        if not visible_at(event, self._verbosity):
            return
        record: dict[str, Any] = {"event": event_name(event), "ts": round(time.time(), 6)}
        record.update(as_dict(event))
        self._stream.write(json.dumps(record, separators=(",", ":"), default=str) + "\n")
        self._stream.flush()

    def close(self) -> None:
        self._stream.flush()
        if self._close_stream:
            self._stream.close()
