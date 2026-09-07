"""F2: human, JSON, and self-contained HTML summaries of one recorded run.

A field this run never actually measured (an old row from before a column existed,
or one a schema migration left null) renders as "unknown" here -- never as a
fabricated `0`, which would read as "measured and it was zero" and is not something
this ever promised. All three renderers share one `_fields()` pass so they can never
disagree about which value came from where.

The HTML is self-contained on purpose: inline `<style>`, no `<script>`, no external
stylesheet or CDN link. It is meant to be opened as a plain file or attached to a bug
report, not served, and it must never execute anything a response body happened to
contain -- every value that could hold arbitrary text (a step's error, in particular,
which often echoes a server's own response) is escaped before it reaches the page.
"""

from __future__ import annotations

import html
import json
import sqlite3
from typing import Any, Literal

Format = Literal["text", "json", "html"]

#: `duration_ms` for a step `_remember` never actually measured (recorded by a build
#: before F1 wrote real numbers) is `0` at the SQL level -- indistinguishable from a
#: `None` by column type alone, since the column has always existed. `0` is a safe
#: signal to treat as "never measured" here because no real request takes exactly
#: `0` milliseconds; unlike `attempts`, whose own unmeasured default (`1`) is also
#: the ordinary, common value for a real step that just happened to succeed on its
#: first try, so it cannot be told apart from real data this way and is not attempted.
_UNKNOWN_IF_ZERO = ("duration_ms",)


def _value(row: sqlite3.Row, key: str) -> Any:
    """A row's own field, or `None` when it was never really measured."""
    value = row[key] if key in row.keys() else None  # noqa: SIM118 - Row.keys() are columns, not values
    if key in _UNKNOWN_IF_ZERO and value in (0, None):
        return None
    return value


def _mark(unknown: str = "—") -> str:
    return unknown


def render_text(run: sqlite3.Row, steps: list[sqlite3.Row], tags: list[str]) -> str:
    lines = [f"{run['name']}  [{run['id']}]", f"  workflow   {run['workflow']}"]
    if run["env"]:
        lines.append(f"  env        {run['env']}")
    lines.append(f"  status     {run['status']} (exit {run['exit_code']})")
    duration = _value(run, "duration_ms")
    lines.append(f"  duration   {f'{duration}ms' if duration is not None else _mark()}")
    if tags:
        lines.append(f"  tags       {', '.join(tags)}")
    if steps:
        lines.append("  steps")
        for step in steps:
            attempts = _value(step, "attempts")
            duration_s = _value(step, "duration_ms")
            lines.append(
                f"    {step['step_id']:<24} {step['status']:<8} "
                f"attempts={attempts if attempts is not None else _mark()} "
                f"duration={f'{duration_s}ms' if duration_s is not None else _mark()}"
            )
    return "\n".join(lines)


def render_json(run: sqlite3.Row, steps: list[sqlite3.Row], tags: list[str]) -> dict[str, Any]:
    return {
        "id": run["id"],
        "name": run["name"],
        "workflow": run["workflow"],
        "env": run["env"],
        "status": run["status"],
        "exit_code": run["exit_code"],
        "duration_ms": _value(run, "duration_ms"),
        # Real run-level aggregates, unlike the per-step fields above: a workflow
        # with no HTTP steps genuinely has `bytes_in == 0`, and most runs genuinely
        # have `retries == 0` -- neither is a fabricated default to hide.
        "bytes_in": run["bytes_in"],
        "retries": run["retries"],
        "tags": list(tags),
        "steps": [
            {
                "step_id": step["step_id"],
                "status": step["status"],
                "lane": step["lane"],
                "attempts": _value(step, "attempts"),
                "duration_ms": _value(step, "duration_ms"),
                "cached": bool(step["cached"]),
                "error": step["error"] or None,
            }
            for step in steps
        ],
    }


def render_json_text(run: sqlite3.Row, steps: list[sqlite3.Row], tags: list[str]) -> str:
    return json.dumps(render_json(run, steps, tags), indent=2) + "\n"


def render_html(run: sqlite3.Row, steps: list[sqlite3.Row], tags: list[str]) -> str:
    e = html.escape

    def cell(step: sqlite3.Row, key: str) -> str:
        value = _value(step, key)
        return str(value) if value is not None else e(_mark())

    duration = _value(run, "duration_ms")
    rows = "\n".join(
        f"<tr><td>{e(step['step_id'])}</td><td>{e(step['status'])}</td>"
        f"<td>{cell(step, 'attempts')}</td>"
        f"<td>{cell(step, 'duration_ms')}</td>"
        f"<td>{e(step['error'] or '')}</td></tr>"
        for step in steps
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{e(run["name"])}</title>
<style>
body {{ font: 14px system-ui, sans-serif; margin: 2rem; color: #1a1a1a; background: #fff; }}
table {{ border-collapse: collapse; margin-top: 1rem; }}
td, th {{ border: 1px solid #ccc; padding: 0.3rem 0.6rem; text-align: left; }}
.status-failed {{ color: #b00020; }}
</style></head>
<body>
<h1>{e(run["name"])}</h1>
<p>id: {e(run["id"])} &middot; workflow: {e(run["workflow"])}</p>
<p class="status-{e(run["status"])}">status: {e(run["status"])} (exit {run["exit_code"]})
&middot; duration: {duration if duration is not None else e(_mark())}ms</p>
<table>
<tr><th>step</th><th>status</th><th>attempts</th><th>duration (ms)</th><th>error</th></tr>
{rows}
</table>
</body></html>
"""


def render(fmt: Format, run: sqlite3.Row, steps: list[sqlite3.Row], tags: list[str]) -> str:
    if fmt == "json":
        return render_json_text(run, steps, tags)
    if fmt == "html":
        return render_html(run, steps, tags)
    return render_text(run, steps, tags)
