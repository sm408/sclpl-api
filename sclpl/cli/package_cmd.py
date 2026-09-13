"""`sclpl package` — build a project into one reproducible, distributable archive."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from sclpl.errors import ValidationError
from sclpl.packages import build as build_mod
from sclpl.packages import install as install_mod
from sclpl.project import context
from sclpl.state.db import default_root

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


@app.command("validate")
def validate(
    archive: Annotated[Path, typer.Argument(help="A .sclplpkg archive.")],
) -> None:
    """Check a package archive without installing or executing anything from it."""
    info = install_mod.validate(archive)
    typer.echo(f"{info.name} {info.version}")
    typer.echo(f"  digest sha256:{info.digest}")
    typer.echo(f"  {len(info.files)} files")


@app.command("install")
def install(
    archive: Annotated[Path, typer.Argument(help="A .sclplpkg archive.")],
    into: Annotated[
        Path | None,
        typer.Option("--into", help="Install root (default: ~/.sclpl/packages)."),
    ] = None,
    json_mode: Annotated[bool, typer.Option("--json", help="Emit the result as JSON.")] = False,
) -> None:
    """Validate, then atomically install a package into `<into>/<name>/<version>`.

    Never executes anything from the archive. A failed install never touches an
    existing good install of the same or a different version.
    """
    result = install_mod.install(archive, into=into or default_root() / "packages")
    if json_mode:
        typer.echo(
            json.dumps(
                {
                    "path": str(result.path),
                    "name": result.name,
                    "version": result.version,
                    "digest": result.digest,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    typer.echo(f"installed {result.name} {result.version}")
    typer.echo(f"  {result.path}")
    typer.echo(f"  digest sha256:{result.digest}")


def _current(project: Path | None) -> context.ProjectContext:
    loaded = context.load(project=project)
    if loaded is None:
        raise ValidationError(f"no {context.MANIFEST} found", remedies=["run sclpl init"])
    return loaded
