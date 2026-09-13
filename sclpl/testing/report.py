"""I5: stable JUnit XML, JSON, and HTML reports for `sclpl test run`.

Report generation is a pure function of already-computed outcomes -- it never
re-runs a test, never touches the network, and never contains a credential:
the data here is exactly the pass/fail/duration/message `sclpl test run`'s own
stderr already shows, reshaped for a CI system or a browser instead of a
terminal.
"""

from __future__ import annotations

import html
import json
import time
from dataclasses import dataclass
from xml.sax.saxutils import escape

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class CaseResult:
    """One test manifest's outcome, ready to render into any report format."""

    name: str
    path: str
    passed: bool
    duration_s: float
    message: str = ""


def to_json(cases: list[CaseResult]) -> str:
    """A stable, versioned JSON summary -- the schema is a compatibility contract."""
    payload = {
        "schema": SCHEMA_VERSION,
        "generated_at": round(time.time(), 3),
        "summary": {
            "total": len(cases),
            "passed": sum(1 for case in cases if case.passed),
            "failed": sum(1 for case in cases if not case.passed),
        },
        "cases": [
            {
                "name": case.name,
                "path": case.path,
                "passed": case.passed,
                "duration_s": case.duration_s,
                "message": case.message,
            }
            for case in cases
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def to_junit_xml(cases: list[CaseResult], *, suite_name: str = "sclpl") -> str:
    """JUnit XML, the format most CI dashboards already know how to render."""
    failures = sum(1 for case in cases if not case.passed)
    total_time = sum(case.duration_s for case in cases)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<testsuite name="{_attr(suite_name)}" tests="{len(cases)}" '
        f'failures="{failures}" time="{total_time:.3f}">',
    ]
    for case in cases:
        lines.append(
            f'  <testcase classname="{_attr(case.path)}" name="{_attr(case.name)}" '
            f'time="{case.duration_s:.3f}">'
        )
        if not case.passed:
            lines.append(f'    <failure message="{_attr(case.message)}"></failure>')
        lines.append("  </testcase>")
    lines.append("</testsuite>")
    return "\n".join(lines) + "\n"


def _attr(text: str) -> str:
    """Escape for a double-quoted XML attribute -- `escape`'s defaults miss `"`."""
    return escape(text, {'"': "&quot;"})


def to_html(cases: list[CaseResult], *, suite_name: str = "sclpl") -> str:
    """A single self-contained HTML file -- no external assets, safe to archive."""
    passed = sum(1 for case in cases if case.passed)
    rows = "\n".join(
        f'<tr class="{"pass" if case.passed else "fail"}">'
        f"<td>{html.escape(case.path)}</td><td>{html.escape(case.name)}</td>"
        f"<td>{'pass' if case.passed else 'fail'}</td>"
        f"<td>{case.duration_s:.3f}s</td><td>{html.escape(case.message)}</td></tr>"
        for case in cases
    )
    title = html.escape(suite_name)
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{title} test report</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
table {{ border-collapse: collapse; width: 100%; }}
td, th {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }}
tr.fail {{ background: #fde8e8; }}
tr.pass {{ background: #e8fde8; }}
</style>
</head>
<body>
<h1>{title} test report</h1>
<p>{passed}/{len(cases)} passed</p>
<table>
<thead><tr><th>path</th><th>name</th><th>result</th><th>duration</th><th>message</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
</body>
</html>
"""
