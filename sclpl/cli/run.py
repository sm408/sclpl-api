"""Request and workflow commands.

M0 implements `call` — one request, one pooled client, results on stdout and progress
on stderr. It exists this early because it exercises the whole reporter path end to
end, which is what every later milestone reports through.

`run`, `validate`, `explain`, `fmt`, and `convert` need the IR and the scheduler; they
are registered in M2 and M4 rather than stubbed here, so `--help` never advertises
something that does not work.
"""

from __future__ import annotations

import asyncio
import sys
import time
from typing import Annotated

import httpx
import typer

from sclpl.cli.options import EXIT_STEP_FAILED, EXIT_USAGE, options_of
from sclpl.render.events import RunFinished, RunStarted, StepFinished, StepStarted
from sclpl.render.plain import format_bytes
from sclpl.render.reporter import Reporter, build_reporter

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")

#: One request has no pool to share, but the ceilings are the ones `run` will use, so
#: `call` and a one-step workflow behave identically against a fussy server.
LIMITS = httpx.Limits(max_connections=32, max_keepalive_connections=16, keepalive_expiry=30.0)


def register(app: typer.Typer) -> None:
    app.command("call", help="Send a single HTTP request. Body to stdout, progress to stderr.")(
        call
    )


def call(
    ctx: typer.Context,
    method: Annotated[str, typer.Argument(help="HTTP method, e.g. GET.")],
    url: Annotated[str, typer.Argument(help="Absolute URL to request.")],
    header: Annotated[
        list[str] | None,
        typer.Option("--header", "-H", help="Request header as 'Name: value'. Repeatable."),
    ] = None,
) -> None:
    verb = method.upper()
    if verb not in METHODS:
        typer.echo(
            f"unknown method {method!r}: expected one of {', '.join(METHODS)}",
            err=True,
        )
        raise typer.Exit(EXIT_USAGE)
    if "://" not in url:
        typer.echo(f"{url!r} is not an absolute URL: it needs a scheme, e.g. https://", err=True)
        raise typer.Exit(EXIT_USAGE)

    try:
        headers = _parse_headers(header or [])
    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(EXIT_USAGE) from error

    options = options_of(ctx)
    reporter = build_reporter(
        verbosity=options.verbosity,
        json_mode=options.json_mode,
        plain=options.plain,
        no_color=options.no_color,
    )
    exit_code = asyncio.run(_call(reporter, verb, url, headers))
    if exit_code:
        raise typer.Exit(exit_code)


def _parse_headers(raw: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in raw:
        name, separator, value = item.partition(":")
        if not separator or not name.strip():
            raise ValueError(f"bad header {item!r}: expected 'Name: value'")
        headers[name.strip()] = value.strip()
    return headers


async def _call(reporter: Reporter, method: str, url: str, headers: dict[str, str]) -> int:
    host = httpx.URL(url).host
    started = time.perf_counter()
    async with reporter:
        reporter.emit(RunStarted(workflow="call", steps_total=1, hosts=(host,)))
        reporter.emit(StepStarted(id=method.lower(), kind="http"))
        step_started = time.perf_counter()
        try:
            async with httpx.AsyncClient(limits=LIMITS, follow_redirects=True) as client:
                response = await client.request(method, url, headers=headers)
        except httpx.HTTPError as error:
            elapsed = _ms(step_started)
            reporter.emit(
                StepFinished(
                    id=method.lower(),
                    status="failed",
                    duration_ms=elapsed,
                    summary=f"{type(error).__name__}: {error}",
                )
            )
            reporter.emit(
                RunFinished(
                    status="failed",
                    duration_ms=_ms(started),
                    counts={"failed": 1},
                    exit_code=EXIT_STEP_FAILED,
                )
            )
            return EXIT_STEP_FAILED

        body = response.content
        summary = f"{response.status_code} {response.reason_phrase} {format_bytes(len(body))}"
        reporter.emit(
            StepFinished(
                id=method.lower(),
                status="ok",
                duration_ms=_ms(step_started),
                summary=summary,
            )
        )
        reporter.emit(
            RunFinished(status="ok", duration_ms=_ms(started), counts={"steps": 1}, exit_code=0)
        )
        # stdout is data (invariant 1): the body, byte for byte, and nothing else.
        await reporter.drain()
        sys.stdout.buffer.write(body)
        if body and not body.endswith(b"\n"):
            sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()
    return 0


def _ms(since: float) -> int:
    return int((time.perf_counter() - since) * 1000)
