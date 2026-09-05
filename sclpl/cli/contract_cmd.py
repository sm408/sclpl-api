"""Local contract inspection and checking commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from sclpl.contracts import check as check_contract
from sclpl.contracts import generate
from sclpl.errors import AssertionFailed, ValidationError

app = typer.Typer(no_args_is_help=True, help="Validate recorded values against contracts.")


def register(root: typer.Typer) -> None:
    root.add_typer(app, name="contract")


@app.command("check")
def check(
    value: Annotated[Path, typer.Argument(help="JSON value or fixture-body file.")],
    contract: Annotated[Path, typer.Argument(help="Local JSON contract file.")],
) -> None:
    """Check local JSON only; this command never fetches contract references."""
    payload = _json(value)
    schema = _json(contract)
    if not isinstance(schema, dict):
        raise ValidationError("contract root must be a JSON object", where=str(contract))
    try:
        check_contract(payload, schema)
    except AssertionFailed as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(error.exit_code) from error
    typer.echo(f"{value}: contract passes", err=True)


@app.command("generate")
def generate_contract(
    value: Annotated[Path, typer.Argument(help="Local JSON sample file.")],
    into: Annotated[
        Path | None, typer.Option("--into", help="Write candidate here; never overwrites.")
    ] = None,
) -> None:
    """Generate a candidate from a local sample without replacing accepted baselines."""
    rendered = json.dumps(generate(_json(value)), indent=2, sort_keys=True) + "\n"
    if into is None:
        typer.echo(rendered)
        return
    if into.exists():
        raise ValidationError(
            f"refusing to overwrite {into}", remedies=["choose a new --into path"]
        )
    into.parent.mkdir(parents=True, exist_ok=True)
    into.write_text(rendered, encoding="utf-8")
    typer.echo(f"wrote candidate {into}", err=True)


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValidationError(f"file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ValidationError(f"invalid JSON: {error}", where=str(path)) from error
