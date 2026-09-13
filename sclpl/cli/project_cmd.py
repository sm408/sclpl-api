"""Create and inspect self-contained sclpl projects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from sclpl.errors import ValidationError
from sclpl.project import context, policy

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

#: I5: an offline CI template. Every step here runs without network access or a
#: credential -- `sclpl test run` executes fixtures, never a live request, and
#: `workflow lock --check`/`project check` are pure local reads. Fixture/contract
#: drift (a real response no longer matching what a test expects) fails the test
#: step with EXIT_STEP_FAILED; a stale lock fails the lock step with
#: EXIT_VALIDATION -- both meaningful, distinct exit codes rather than one
#: generic failure.
_CI_TEMPLATE = """name: sclpl checks

on:
  push:
  pull_request:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install
        run: python -m pip install sclpl

      - name: Verify workflow locks are current
        run: sclpl workflow lock --check

      - name: Verify project configuration
        run: sclpl project check

      - name: Run project tests (offline, fixture-based)
        run: >
          sclpl test run
          --junit test-results.xml
          --json test-results.json
          --html test-results.html

      - name: Upload test reports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: sclpl-test-reports
          path: |
            test-results.xml
            test-results.json
            test-results.html
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


@project_app.command("ci-template")
def ci_template(
    out: Annotated[
        Path, typer.Option("--out", help="Where to write it.")
    ] = Path(".github/workflows/sclpl-ci.yml"),
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Replace an existing file.")
    ] = False,
) -> None:
    """Write a ready-to-use, offline GitHub Actions workflow for this project.

    Every step runs without network access or a credential: `sclpl test run`
    executes fixtures rather than a live request, and `workflow lock --check`/
    `project check` are pure local reads. Fixture/contract drift fails with
    `EXIT_STEP_FAILED`; a stale lock fails with `EXIT_VALIDATION` -- distinct,
    meaningful exit codes rather than one generic failure.
    """
    if out.exists() and not overwrite:
        raise ValidationError(f"{out} already exists", remedies=["pass --overwrite to replace it"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_CI_TEMPLATE, encoding="utf-8")
    typer.echo(f"wrote {out}", err=True)


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
    resolved_policy = policy.parse(loaded)  # raises on a malformed [policy] table
    allowed_hosts = resolved_policy.allowed_hosts
    payload = loaded.describe()
    payload["policy"] = {
        "hosts": sorted(allowed_hosts) if allowed_hosts is not None else None,
        "output_roots": [str(root) for root in resolved_policy.output_roots],
        "overwrite": resolved_policy.overwrite,
        "deny_capabilities": sorted(resolved_policy.deny_capabilities),
    }
    if json_mode:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(f"project: {payload['root']}")
    typer.echo(f"environment: {loaded.environment} ({loaded.environment_source})")
    typer.echo("manifest: valid")
    if resolved_policy.restricts_hosts:
        typer.echo(f"policy hosts: {', '.join(sorted(resolved_policy.allowed_hosts or ()))}")
    if resolved_policy.output_roots:
        roots = ", ".join(str(root) for root in resolved_policy.output_roots)
        typer.echo(f"policy output roots: {roots}")
    if not resolved_policy.overwrite:
        typer.echo("policy overwrite: denied (pass --overwrite to run to override)")
    if resolved_policy.deny_capabilities:
        denied = ", ".join(sorted(resolved_policy.deny_capabilities))
        typer.echo(f"policy deny capabilities: {denied}")


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
