"""Create and inspect self-contained sclpl projects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from sclpl.errors import ValidationError
from sclpl.project import context

project_app = typer.Typer(no_args_is_help=True, help="Inspect the current project.")
env_app = typer.Typer(no_args_is_help=True, help="Select project environments.")

_MANIFEST = """[project]
schema = 1
name = "{name}"
default_environment = "default"

[workflows]
paths = ["workflows"]

[environments.default]

[environments.default.settings]
base_url = "https://example.invalid"
"""


def register(root: typer.Typer) -> None:
    root.command("init", help="Create a project without overwriting files.")(init)
    root.add_typer(project_app, name="project")
    root.add_typer(env_app, name="env")


def init(
    path: Annotated[Path, typer.Argument(help="Directory to initialize.")] = Path("."),
) -> None:
    root = path.resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest = root / context.MANIFEST
    if manifest.exists():
        raise ValidationError(
            f"{manifest} already exists", remedies=["use project check to inspect it"]
        )
    (root / "workflows").mkdir(exist_ok=True)
    (root / "fixtures").mkdir(exist_ok=True)
    (root / ".sclpl").mkdir(exist_ok=True)
    manifest.write_text(_MANIFEST.format(name=root.name), encoding="utf-8")
    ignore = root / ".gitignore"
    existing = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
    missing = [item for item in (".sclpl/", "outputs/") if item not in existing.splitlines()]
    if missing:
        ignore.write_text(
            existing.rstrip() + ("\n" if existing.strip() else "") + "\n".join(missing) + "\n",
            encoding="utf-8",
        )
    typer.echo(f"initialized {root}")


@project_app.command("check")
def check(
    json_mode: Annotated[
        bool, typer.Option("--json", help="Emit resolved context as JSON.")
    ] = False,
    project: Annotated[
        Path | None, typer.Option("--project", help="Project root or manifest.")
    ] = None,
    env: Annotated[str | None, typer.Option("--env", help="Environment to resolve.")] = None,
) -> None:
    loaded = context.load(project=project, env=env)
    if loaded is None:
        raise ValidationError(f"no {context.MANIFEST} found", remedies=["run sclpl init"])
    payload = loaded.describe()
    if json_mode:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(f"project: {payload['root']}")
    typer.echo(f"environment: {loaded.environment} ({loaded.environment_source})")
    typer.echo("manifest: valid")


@env_app.command("list")
def env_list() -> None:
    loaded = _current()
    for name in sorted(context._table(loaded.manifest, "environments")):
        typer.echo(f"{'*' if name == loaded.environment else ' '} {name}")


@env_app.command("show")
def env_show(name: Annotated[str, typer.Argument()]) -> None:
    loaded = context.load(env=name)
    assert loaded is not None
    typer.echo(json.dumps(loaded.describe(), indent=2, sort_keys=True))


@env_app.command("use")
def env_use(name: Annotated[str, typer.Argument()]) -> None:
    loaded = context.load(env=name)
    assert loaded is not None
    selection = loaded.root / context.SELECTION
    selection.parent.mkdir(parents=True, exist_ok=True)
    selection.write_text(name + "\n", encoding="utf-8")
    typer.echo(f"selected {name}")


def _current() -> context.ProjectContext:
    loaded = context.load()
    if loaded is None:
        raise ValidationError(f"no {context.MANIFEST} found", remedies=["run sclpl init"])
    return loaded
