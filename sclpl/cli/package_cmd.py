"""`sclpl package` — build a project into one reproducible, distributable archive."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from sclpl.errors import ValidationError
from sclpl.packages import build as build_mod
from sclpl.packages import install as install_mod
from sclpl.packages import lifecycle
from sclpl.packages import registry as registry_mod
from sclpl.packages import release as release_mod
from sclpl.project import context
from sclpl.state.db import default_root

IntoOption = Annotated[
    Path | None, typer.Option("--into", help="Install root (default: ~/.sclpl/packages).")
]

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
    into: IntoOption = None,
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


@app.command("list")
def list_command(into: IntoOption = None) -> None:
    """Every installed package under the install root."""
    root = into or default_root() / "packages"
    installed = lifecycle.list_installed(root)
    if not installed:
        typer.echo("no packages installed", err=True)
        return
    width = max(len(item.name) for item in installed)
    for item in installed:
        typer.echo(f"{item.name:<{width}} {item.version:<12} sha256:{item.digest}")


@app.command("show")
def show(
    name: Annotated[str, typer.Argument()],
    version: Annotated[str, typer.Argument()],
    into: IntoOption = None,
) -> None:
    """Everything recorded about one installed package at install time."""
    root = into or default_root() / "packages"
    manifest = lifecycle.describe(root, name, version)
    typer.echo(json.dumps(manifest, indent=2, sort_keys=True))


@app.command("verify")
def verify(
    name: Annotated[str, typer.Argument()],
    version: Annotated[str, typer.Argument()],
    into: IntoOption = None,
) -> None:
    """Re-hash an installed package's files against its own recorded manifest.

    Unlike `package validate` (an archive, before installing), this checks the
    files actually on disk today -- it catches drift after installation, not
    just a corrupt or tampered archive before it.
    """
    root = into or default_root() / "packages"
    lifecycle.verify(root, name, version)
    typer.echo(f"{name} {version}: ok")


@app.command("remove")
def remove(
    name: Annotated[str, typer.Argument()],
    version: Annotated[str, typer.Argument()],
    into: IntoOption = None,
    force: Annotated[
        bool, typer.Option("--force", help="Remove even if the current project pins it.")
    ] = False,
    project: Annotated[
        Path | None, typer.Option("--project", help="Project root or manifest.")
    ] = None,
) -> None:
    """Remove one installed package version.

    Refused, without --force, while the current project's [package.requires]
    pins this exact name and version -- a referenced version cannot silently
    disappear.
    """
    root = into or default_root() / "packages"
    lifecycle.remove(root, name, version, required_by=_requires(project), force=force)
    typer.echo(f"removed {name} {version}")


@app.command("update")
def update(
    archive: Annotated[Path, typer.Argument(help="A .sclplpkg archive.")],
    into: IntoOption = None,
) -> None:
    """Install a new version alongside any existing ones, and show what changed.

    Never removes or silently replaces a previously installed version -- a run
    that referenced the old version keeps working until something explicitly
    removes it (`package remove`) or changes what it references.
    """
    root = into or default_root() / "packages"
    result = install_mod.install(archive, into=root)
    previous = sorted(
        item.version
        for item in lifecycle.list_installed(root)
        if item.name == result.name and item.version != result.version
    )
    if not previous:
        typer.echo(f"installed {result.name} {result.version} (first install)")
        return
    changes = lifecycle.diff(root, result.name, previous[-1], result.version)
    typer.echo(f"installed {result.name} {result.version} (previously {previous[-1]})")
    if changes.is_empty:
        typer.echo("  no file differences")
        return
    for name in changes.added:
        typer.echo(f"  + {name}")
    for name in changes.removed:
        typer.echo(f"  - {name}")
    for name in changes.changed:
        typer.echo(f"  ~ {name}")


@app.command("pull")
def pull(
    name: Annotated[str, typer.Argument()],
    version: Annotated[str, typer.Argument()],
    from_registry: Annotated[
        str, typer.Option("--registry", help="A local directory path or an https:// base URL.")
    ],
    into: IntoOption = None,
    offline: Annotated[
        bool, typer.Option("--offline", help="Only use the local registry cache.")
    ] = False,
    json_mode: Annotated[bool, typer.Option("--json", help="Emit the result as JSON.")] = False,
) -> None:
    """Fetch a package from a registry index, then install it.

    The downloaded artifact's own bytes are hashed and checked against the
    registry's declared digest before installation ever sees it -- a registry
    serving something other than what it advertised is refused. A private
    HTTPS registry authenticates with a bearer token from SCLPL_REGISTRY_TOKEN;
    the token is never written to the index, the cache, or a log line.
    """
    cache = default_root() / "registry-cache"
    fetched = registry_mod.fetch(from_registry, name, version, cache=cache, offline=offline)
    result = install_mod.install(fetched.path, into=into or default_root() / "packages")
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
    typer.echo(f"installed {result.name} {result.version} from {from_registry}")
    typer.echo(f"  {result.path}")
    typer.echo(f"  digest sha256:{result.digest}")


@app.command("release-index")
def release_index(
    source: Annotated[
        Path, typer.Argument(help="Directory containing already-built .sclplpkg archives.")
    ],
    out: Annotated[
        Path, typer.Option("--out", help="Directory to stage the index and artifacts into.")
    ],
    json_mode: Annotated[bool, typer.Option("--json", help="Emit the result as JSON.")] = False,
) -> None:
    """Stage a registry index.json plus its artifacts for an existing team tool to publish.

    Never uploads or publishes anything -- that stays a separate, explicit step
    using whatever a team already deploys files with (blob storage, an internal
    HTTP server, GitHub Pages, ...). Two archives claiming the same name and
    version with different content are refused, not silently resolved by
    keeping whichever was scanned last.
    """
    archives = sorted(source.glob("*.sclplpkg"))
    if not archives:
        raise ValidationError(f"no .sclplpkg archives found under {source}")
    result = release_mod.build_index(archives, out=out)
    if json_mode:
        typer.echo(
            json.dumps(
                {
                    "index": str(result.index_path),
                    "packages": [{"name": n, "version": v} for n, v in result.entries],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    typer.echo(f"staged {len(result.entries)} package version(s) at {result.index_path}")
    for name, version in result.entries:
        typer.echo(f"  {name} {version}")


def _requires(project: Path | None) -> dict[str, str] | None:
    loaded = context.load(project=project)
    if loaded is None:
        return None
    requires = loaded.package.get("requires", {})
    return requires if isinstance(requires, dict) else None


def _current(project: Path | None) -> context.ProjectContext:
    loaded = context.load(project=project)
    if loaded is None:
        raise ValidationError(f"no {context.MANIFEST} found", remedies=["run sclpl init"])
    return loaded
