"""Catalogue commands: import, list, show, remove."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated

import typer

from sclpl.catalog import resolve as resolver
from sclpl.catalog import store
from sclpl.errors import SclplError, ValidationError
from sclpl.importers import curl as curl_importer
from sclpl.importers import openapi as openapi_importer
from sclpl.importers import postman as postman_importer
from sclpl.run.preflight import preflight

app = typer.Typer(help="Register and inspect workflows.", no_args_is_help=True)


def register(root: typer.Typer) -> None:
    root.command("import", help="Register a workflow file.")(import_workflow)
    root.command("list", help="List registered and local workflows.")(list_workflows)
    root.command("show", help="Show a workflow's ports, modes, and steps.")(show)
    root.command("remove", help="Unregister a workflow.")(remove)


ScopeOpt = Annotated[
    str,
    typer.Option("--scope", help="Where to register it: project or user."),
]


def import_workflow(
    source: Annotated[Path, typer.Argument(help="Workflow file to register.")],
    name: Annotated[str | None, typer.Option("--as", help="Register under this name.")] = None,
    scope: ScopeOpt = "project",
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Replace without keeping the previous version.")
    ] = False,
    from_format: Annotated[
        str | None,
        typer.Option(
            "--from",
            help="Source format: a plain workflow file is registered as-is; 'curl' parses a"
            " saved curl command; 'openapi' parses one operation from a local JSON OpenAPI"
            " 3.x document (see --operation); 'postman' parses one request from a local"
            " Postman v2.1 collection (see --request and --environment).",
        ),
    ] = None,
    operation: Annotated[
        str | None,
        typer.Option("--operation", help="OpenAPI operationId to import (with --from openapi)."),
    ] = None,
    request: Annotated[
        str | None,
        typer.Option(
            "--request", help="Postman request name, 'Folder/Name' if nested (with --from postman)."
        ),
    ] = None,
    environment: Annotated[
        Path | None,
        typer.Option(
            "--environment", help="A Postman environment file to merge (with --from postman)."
        ),
    ] = None,
) -> None:
    if scope not in ("project", "user"):
        typer.echo(f"unknown scope {scope!r}: expected 'project' or 'user'", err=True)
        raise typer.Exit(2)
    if from_format not in (None, "curl", "openapi", "postman"):
        raise ValidationError(
            f"unknown --from format {from_format!r}", remedies=["expected: curl, openapi, postman"]
        )

    try:
        if from_format == "curl":
            entry = _import_curl(source, name=name, scope=scope, overwrite=overwrite)
        elif from_format == "openapi":
            if not operation:
                raise ValidationError(
                    "--operation is required with --from openapi",
                    remedies=["pass the OpenAPI operationId to import"],
                )
            entry = _import_openapi(source, operation, name=name, scope=scope, overwrite=overwrite)
        elif from_format == "postman":
            if not request:
                raise ValidationError(
                    "--request is required with --from postman",
                    remedies=["pass the Postman request name to import"],
                )
            entry = _import_postman(
                source, request, environment, name=name, scope=scope, overwrite=overwrite
            )
        else:
            entry = store.import_workflow(source, scope=scope, name=name, overwrite=overwrite)
    except SclplError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(error.exit_code) from error
    typer.echo(f"registered {entry.name} ({entry.steps} steps) at {entry.path}", err=True)


def _import_curl(source: Path, *, name: str | None, scope: str, overwrite: bool) -> store.Entry:
    """Convert a saved curl command into a workflow, then register it normally.

    Never runs the command. A credential the command carried is reported once,
    on stderr, for the operator to register with a secret store themselves --
    it is never written into the generated workflow, the manifest, or the catalog.
    """
    command = source.read_text(encoding="utf-8")
    parsed = curl_importer.parse(command)
    workflow_name = name or source.stem
    result = curl_importer.render(parsed, name=workflow_name)
    _report_import(
        result.warnings, result.auth_manifest, result.extracted_secret, source="the command"
    )
    return _register_rendered(
        result.workflow, workflow_name, name=name, scope=scope, overwrite=overwrite
    )


def _report_import(
    warnings: tuple[str, ...],
    auth_manifest: str | None,
    extracted_secret: tuple[str, str] | None,
    *,
    source: str,
) -> None:
    for warning in warnings:
        typer.echo(f"warning: {warning}", err=True)
    if auth_manifest:
        typer.echo("add this to your project manifest (sclpl.toml):", err=True)
        typer.echo(auth_manifest, err=True)
    if extracted_secret:
        secret_name, _ = extracted_secret
        typer.echo(
            f"a credential was extracted from {source} into an auth reference; "
            "this tool never prints or stores it -- copy it from the original "
            f"source yourself and run: sclpl secret set {secret_name}",
            err=True,
        )


def _register_rendered(
    workflow: str, workflow_name: str, *, name: str | None, scope: str, overwrite: bool
) -> store.Entry:
    with tempfile.TemporaryDirectory() as scratch:
        rendered = Path(scratch) / f"{workflow_name}.sclpll"
        rendered.write_text(workflow, encoding="utf-8")
        return store.import_workflow(rendered, scope=scope, name=name, overwrite=overwrite)


def _import_openapi(
    source: Path, operation_id: str, *, name: str | None, scope: str, overwrite: bool
) -> store.Entry:
    """Convert one operation of a local JSON OpenAPI 3.x document into a workflow.

    Never fetches anything: only `#/...` references within the same document
    are resolved. A required path/query parameter with no default becomes a
    `@var` the generated workflow documents as required via `--var`.
    """
    document = openapi_importer.load(source)
    workflow_name = name or operation_id
    result = openapi_importer.render(document, operation_id, name=workflow_name)
    _report_import(result.warnings, None, None, source="the document")
    return _register_rendered(
        result.workflow, workflow_name, name=name, scope=scope, overwrite=overwrite
    )


def _import_postman(
    source: Path,
    request_name: str,
    environment: Path | None,
    *,
    name: str | None,
    scope: str,
    overwrite: bool,
) -> store.Entry:
    """Convert one request of a local Postman v2.1 collection into a workflow.

    Never fetches anything and never evaluates a pre-request or test script --
    both are reported as diagnostics only. A credential in the request's own
    `auth` block, or an environment variable marked `"type": "secret"`, is
    handled the same way as curl's: reported once, never written to disk.
    """
    collection = postman_importer.load(source, environment=environment)
    workflow_name = name or request_name.rsplit("/", 1)[-1]
    result = postman_importer.render(collection, request_name, name=workflow_name)
    _report_import(
        result.warnings, result.auth_manifest, result.extracted_secret, source="the request"
    )
    return _register_rendered(
        result.workflow, workflow_name, name=name, scope=scope, overwrite=overwrite
    )


def list_workflows(
    scope: Annotated[str | None, typer.Option("--scope", help="project or user.")] = None,
) -> None:
    """Everything resolvable, registered or local.

    Local files are listed too: they are what `sclpl <name>` would actually run, and a
    listing that only showed the registered ones would be misleading.
    """
    registered = {entry.name: entry for entry in store.entries(scope)}
    local = resolver.available()

    if not registered and not local:
        typer.echo("no workflows found", err=True)
        typer.echo("import one:  sclpl import <file.sclpll>", err=True)
        return

    typer.echo(f"{'name':<24} {'steps':>5}  {'where':<10} description")
    typer.echo(f"{'-' * 24} {'-' * 5}  {'-' * 10} {'-' * 30}")
    for name in sorted(set(registered) | set(local)):
        entry = registered.get(name)
        if entry is not None and name not in local:
            typer.echo(f"{name:<24} {entry.steps:>5}  {entry.scope:<10} {entry.description[:30]}")
        else:
            path = local.get(name)
            steps = entry.steps if entry else _count(path)
            typer.echo(f"{name:<24} {steps:>5}  {'local':<10} {path}")


def _count(path: Path | None) -> int:
    if path is None:
        return 0
    try:
        return len(resolver.load(path).all_steps())
    except Exception:  # noqa: BLE001 - a broken file still belongs in the listing
        return 0


def show(
    workflow: Annotated[str, typer.Argument(help="Workflow name or path.")],
) -> None:
    try:
        located = resolver.resolve(workflow)
    except SclplError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(error.exit_code) from error

    doc = located.doc
    typer.echo(f"{doc.name}  ({located.source}: {located.path})")
    if doc.description:
        typer.echo(f"  {doc.description}")

    if doc.inputs or doc.outputs:
        typer.echo("\nports:")
        for port in doc.inputs:
            flag = "" if port.required else "  (optional)"
            typer.echo(f"  in   {port.name:<20} {port.format}{flag}")
        for port in doc.outputs:
            flag = "" if port.required else "  (optional)"
            typer.echo(f"  out  {port.name:<20} {port.format}{flag}")

    if doc.modes:
        typer.echo("\nmodes:")
        for name, mode in doc.modes.items():
            marker = " (default)" if name == doc.default_mode else ""
            detail = mode.description or ("all steps" if mode.all else ", ".join(mode.include))
            typer.echo(f"  {name:<20} {detail[:44]}{marker}")

    typer.echo(f"\nsteps ({len(doc.all_steps())}):")
    for step in doc.all_steps():
        needs = f" <- {', '.join(step.needs)}" if step.needs else ""
        tags = f"  [{', '.join(step.tags)}]" if step.tags else ""
        typer.echo(f"  {step.id:<24} {step.kind:<10}{needs}{tags}")

    report = preflight(doc, check_files=False, require_ports=False)
    if report.ok:
        typer.echo(f"\nvalidates: {report.summary()}")
    else:
        typer.echo(f"\ndoes not validate: {report.problems[0].diagnostic.message}")


def remove(
    workflow: Annotated[str, typer.Argument(help="Registered workflow name.")],
    scope: ScopeOpt = "project",
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Do not ask.")] = False,
) -> None:
    try:
        entry = store.find(workflow, scope)
    except SclplError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(error.exit_code) from error

    # Nothing destructive without naming the target (SPEC section 15).
    if not yes and not typer.confirm(f"remove {entry.name} ({entry.path})?", default=False):
        typer.echo("cancelled", err=True)
        raise typer.Exit(0)

    path = store.remove(workflow, scope)
    typer.echo(
        f"removed {path} (a copy is kept under {store.root(scope) / store.VERSIONS})", err=True
    )
