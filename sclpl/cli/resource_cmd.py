"""Inspect provider-backed resources without adding provider-specific CLI branches."""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Annotated

import typer

from sclpl.errors import SclplError
from sclpl.ext.resources import display_resource_uri, resource_provider, resource_providers
from sclpl.run.resources import recover as recover_remote

app = typer.Typer(help="Inspect remote resource providers and prefixes.", no_args_is_help=True)


def register(root: typer.Typer) -> None:
    root.add_typer(app, name="resource")


@app.command("providers")
def providers() -> None:
    """List registered resource providers and their supported operations."""
    found = resource_providers()
    if not found:
        typer.echo("no resource providers registered")
        return
    typer.echo(f"{'scheme':<12} read write list revisions conditional-write server-copy")
    for provider in found:
        caps = provider.capabilities()
        flags = (
            caps.read,
            caps.write,
            caps.list,
            caps.revisions,
            caps.conditional_write,
            caps.server_copy,
        )
        typer.echo(f"{provider.scheme:<12} " + " ".join("yes" if flag else "no" for flag in flags))


@app.command("stat")
def stat(uri: Annotated[str, typer.Argument(help="A provider resource URI.")]) -> None:
    """Show provider-neutral metadata for one object."""
    try:
        provider = resource_provider(uri)
        info = provider.stat(uri)
    except SclplError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(error.exit_code) from error
    typer.echo(f"uri: {display_resource_uri(info.uri)}")
    typer.echo(f"size: {info.size if info.size is not None else '-'}")
    typer.echo(f"modified: {info.modified.isoformat() if info.modified else '-'}")
    typer.echo(f"revision: {info.revision or '-'}")
    typer.echo(f"content-type: {info.content_type or '-'}")
    if info.metadata:
        typer.echo("metadata:")
        for key, value in sorted(info.metadata.items()):
            typer.echo(f"  {key}: {value}")


@app.command("ls")
def ls(
    uri: Annotated[str, typer.Argument(help="A provider prefix URI.")],
    pattern: Annotated[
        str | None,
        typer.Option("--glob", help="Optional provider-neutral glob against each logical URI."),
    ] = None,
) -> None:
    """List a provider prefix in stable URI order."""
    try:
        provider = resource_provider(uri)
        entries = sorted(provider.list(uri), key=lambda item: item.uri)
    except SclplError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(error.exit_code) from error
    for info in entries:
        if pattern is not None and not fnmatchcase(info.uri, pattern):
            continue
        size = str(info.size) if info.size is not None else "-"
        revision = info.revision or "-"
        typer.echo(f"{size:>12}  {revision:<20}  {display_resource_uri(info.uri)}")


@app.command("doctor")
def doctor(uri: Annotated[str, typer.Argument(help="A readable provider object URI.")]) -> None:
    """Verify installed provider, credentials, and read access without writing."""
    try:
        provider = resource_provider(uri)
        info = provider.stat(uri)
    except SclplError as error:
        typer.echo(f"provider: failed\n{error}", err=True)
        raise typer.Exit(error.exit_code) from error
    caps = provider.capabilities()
    typer.echo(f"provider: {provider.scheme} (loaded)")
    typer.echo("authentication: usable")
    typer.echo(f"read: yes ({display_resource_uri(info.uri)})")
    typer.echo(f"write: {'supported' if caps.write else 'not supported'}")
    typer.echo(f"list: {'supported' if caps.list else 'not supported'}")
    typer.echo(f"conditional-write: {'supported' if caps.conditional_write else 'not supported'}")
    typer.echo(f"distributed-locks: {'supported' if caps.locks else 'not supported'}")
    typer.echo(f"server-copy: {'supported' if caps.server_copy else 'not supported'}")


@app.command("recover")
def recover(
    run_id: Annotated[str, typer.Argument(help="Interrupted remote publication run ID.")],
) -> None:
    """Verify and complete a fixed-output remote publication left interrupted."""
    try:
        report = recover_remote(run_id)
    except SclplError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(error.exit_code) from error
    if not report.found:
        typer.echo(f"{run_id}: no pending remote publication")
        return
    if report.already_published:
        typer.echo(f"already-published: {', '.join(report.already_published)}")
    if report.completed:
        typer.echo(f"completed: {', '.join(report.completed)}")
