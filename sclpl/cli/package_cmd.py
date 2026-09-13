"""`sclpl package` — build a project into one reproducible, distributable archive."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from sclpl.errors import ValidationError
from sclpl.packages import build as build_mod
from sclpl.project import context

app = typer.Typer(no_args_is_help=True, help="Build and inspect distributable SCLPL packages.")


def register(root: typer.Typer) -> None:
    root.add_typer(app, name="package")


@app.command("build")
def build(
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Archive path (default: dist/<name>-<version>.sclplpkg)"),
    ] = None,
    project: Annotated[
        Path | None, typer.Option("--project", help="Project root or manifest.")
    ] = None,
    json_mode: Annotated[bool, typer.Option("--json", help="Emit the result as JSON.")] = False,
) -> None:
    """Bundle the current project's declared surface into one archive.

    Building never runs project code -- it only reads and hashes files. Two builds
    of unchanged content produce byte-identical archives, so a package's own digest
    is a reliable "did anything change" signal without re-downloading it.
    """
    loaded = _current(project)
    if not loaded.package:
        raise ValidationError(
            "no [package] table in the project manifest",
            where=str(loaded.manifest_path),
            remedies=['add [package]\nname = "..."\nversion = "..."'],
        )
    result = build_mod.build(loaded, out=out)
    if json_mode:
        typer.echo(
            json.dumps(
                {
                    "path": str(result.path),
                    "name": result.name,
                    "version": result.version,
                    "digest": result.digest,
                    "files": list(result.files),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    typer.echo(f"built {result.path}")
    typer.echo(f"  {result.name} {result.version}")
    typer.echo(f"  digest sha256:{result.digest}")
    typer.echo(f"  {len(result.files)} files")


def _current(project: Path | None) -> context.ProjectContext:
    loaded = context.load(project=project)
    if loaded is None:
        raise ValidationError(f"no {context.MANIFEST} found", remedies=["run sclpl init"])
    return loaded
