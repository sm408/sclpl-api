"""Request and workflow commands.

`call` sends one request through the same pooled transport a workflow uses, so its
retry behaviour, its timeouts, and its diagnostics are the ones a one-step workflow
would get. That is the point of it being here rather than being a separate little
client.

`run`, `validate`, `explain`, `fmt`, and `convert` arrive with the IR in M4; they are
not registered until they work, so `--help` never advertises something that does not.
"""

from __future__ import annotations

import asyncio
import sys
import time
from typing import Annotated, Any

import httpx
import typer

from sclpl.cli.options import options_of
from sclpl.errors import EXIT_STEP_FAILED, EXIT_USAGE, SclplError
from sclpl.render.events import RunFinished, RunStarted, StepFinished, StepStarted
from sclpl.render.reporter import Reporter, build_reporter
from sclpl.run.retry import Retry
from sclpl.run.transport import Pool, TransportLimits, summarise

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")


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
    data: Annotated[
        str | None,
        typer.Option("--data", "-d", help="Request body. Sent as JSON when it parses as JSON."),
    ] = None,
    retries: Annotated[
        int, typer.Option("--retries", help="Attempts after the first, on 429/5xx and timeouts.")
    ] = 2,
    timeout: Annotated[
        float, typer.Option("--timeout", help="Seconds to wait per attempt.")
    ] = 30.0,
) -> None:
    verb = method.upper()
    if verb not in METHODS:
        typer.echo(f"unknown method {method!r}: expected one of {', '.join(METHODS)}", err=True)
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
    exit_code = asyncio.run(_call(reporter, verb, url, headers, data, Retry(max=retries), timeout))
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


def _body_kwargs(data: str | None) -> dict[str, Any]:
    """Send a body as JSON when it is JSON, and as bytes otherwise.

    Guessing is right here: someone passing `-d '{"a":1}'` means JSON, and making them
    also pass a Content-Type would be ceremony.
    """
    if data is None:
        return {}
    import json

    try:
        return {"json": json.loads(data)}
    except json.JSONDecodeError:
        return {"content": data.encode()}


async def _call(
    reporter: Reporter,
    method: str,
    url: str,
    headers: dict[str, str],
    data: str | None,
    retry: Retry,
    timeout: float,
) -> int:
    host = httpx.URL(url).host
    step = method.lower()
    started = time.perf_counter()
    async with reporter:
        reporter.emit(RunStarted(workflow="call", steps_total=1, hosts=(host,)))
        reporter.emit(StepStarted(id=step, kind="http"))
        step_started = time.perf_counter()

        async with Pool(TransportLimits(timeout=timeout), retry) as pool:
            try:
                attempt = await pool.request(
                    method,
                    url,
                    reporter=reporter,
                    step=step,
                    headers=headers or None,
                    **_body_kwargs(data),
                )
            except (SclplError, httpx.HTTPError) as error:
                reporter.emit(
                    StepFinished(
                        id=step,
                        status="failed",
                        duration_ms=_ms(step_started),
                        summary=_summarise_error(error),
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

        response = attempt.response
        body = response.content
        reporter.emit(
            StepFinished(
                id=step,
                status="ok",
                duration_ms=attempt.duration_ms,
                summary=summarise(response, attempt.attempts),
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


def _summarise_error(error: BaseException) -> str:
    if isinstance(error, SclplError):
        return error.diagnostic.message
    return f"{type(error).__name__}: {error}"


def _ms(since: float) -> int:
    return int((time.perf_counter() - since) * 1000)
