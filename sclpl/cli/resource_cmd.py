"""Inspect provider-backed resources without adding provider-specific CLI branches."""

from __future__ import annotations

from typing import Annotated

import typer

from sclpl.errors import SclplError
from sclpl.ext.resources import display_resource_uri, resource_provider, resource_providers

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
    typer.echo(f"{'scheme':<12} read write list revisions conditional-write")
    for provider in found:
        caps = provider.capabilities()
        flags = (caps.read, caps.write, caps.list, caps.revisions, caps.conditional_write)
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


@app.command("ls")
def ls(uri: Annotated[str, typer.Argument(help="A provider prefix URI.")]) -> None:
    """List a provider prefix in stable URI order."""
    try:
        provider = resource_provider(uri)
        entries = sorted(provider.list(uri), key=lambda item: item.uri)
    except SclplError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(error.exit_code) from error
    for info in entries:
        size = str(info.size) if info.size is not None else "-"
        revision = info.revision or "-"
        typer.echo(f"{size:>12}  {revision:<20}  {display_resource_uri(info.uri)}")
