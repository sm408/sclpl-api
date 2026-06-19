from __future__ import annotations

import asyncio
import csv
import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from app.core.engine.hooks import FunctionHookRunner
from app.core.engine.variable_resolver import DefaultVariableResolver
from app.core.models.context import ExecutionContext
from app.core.models.environment import Environment, Variable
from app.core.models.plugin import PluginStatus
from app.core.models.request import HttpMethod, RequestParam
from app.core.models.workflow import RetryConfig, RetryStrategy, StepType, WorkflowDef, WorkflowStep
from app.ui.app import App

app = typer.Typer(
    name="sclplapi",
    help="Local-first, Python-first API workflow studio",
    no_args_is_help=True,
)
console = Console()

DB_OPTION = typer.Option("data/sclplapi.db", "--db", help="Database path")


def _run(coro):
    return asyncio.run(coro)


def _dict_to_env(d: dict) -> Environment:
    variables = [
        Variable(key=v["key"], value=v["value"], is_secret=bool(v.get("is_secret", 0)))
        for v in d.get("variables", [])
    ]
    return Environment(id=d["id"], name=d["name"], variables=variables)


def _print_response(status_code, headers, body, duration_ms, error):
    if error:
        console.print(f"[red]Error: {error}[/red]")
        return
    color = "green" if status_code < 400 else "red"
    console.print(f"[{color}]{status_code}[/{color}] {duration_ms}ms")
    console.print()
    try:
        parsed = json.loads(body)
        console.print_json(json.dumps(parsed, indent=2))
    except (json.JSONDecodeError, TypeError):
        if body:
            console.print(body[:2000])


def _parse_headers(headers_raw: list[str]) -> list[RequestParam]:
    parsed = []
    for h in headers_raw:
        key, _, value = h.partition(":")
        parsed.append(RequestParam(key=key.strip(), value=value.strip()))
    return parsed


async def _get_active_env(application) -> tuple[dict | None, dict[str, str]]:
    env = await application.environments.get_active()
    variables: dict[str, str] = {}
    if env:
        for v in env.get("variables", []):
            variables[v["key"]] = v["value"]
    return env, variables


async def _resolve_ctx(application, env_name: str | None = None, use_active: bool = True) -> tuple[dict | None, ExecutionContext]:
    env = None
    variables: dict[str, str] = {}

    if env_name:
        envs = await application.environments.list_all()
        env = next((e for e in envs if e["name"] == env_name), None)
        if not env:
            console.print(f"[red]Environment '{env_name}' not found[/red]")
            raise typer.Exit(1)
        for v in env.get("variables", []):
            variables[v["key"]] = v["value"]
    elif use_active:
        env, variables = await _get_active_env(application)

    resolver = DefaultVariableResolver()
    ctx = ExecutionContext(
        environment=_dict_to_env(env) if env else None,
        variables=variables,
    )
    ctx.variables = resolver.build_variable_map(ctx)
    return env, ctx


# ──────────────────────────────────────────────────────────────────────
# RUN
# ──────────────────────────────────────────────────────────────────────

@app.command()
def run(
    url: str = typer.Argument(help="Request URL"),
    method: str = typer.Option("GET", "-m", "--method", help="HTTP method"),
    header: list[str] = typer.Option([], "-H", "--header", help="Headers (Key:Value)"),
    body: str | None = typer.Option(None, "-b", "--body", help="Request body"),
    body_type: str | None = typer.Option(None, help="Body type: json, form, raw"),
    auth_type: str | None = typer.Option(None, help="Auth type: bearer, basic, api_key"),
    auth_token: str | None = typer.Option(None, help="Auth token (bearer)"),
    auth_user: str | None = typer.Option(None, help="Auth username (basic)"),
    auth_pass: str | None = typer.Option(None, help="Auth password (basic)"),
    auth_key: str | None = typer.Option(None, help="API key value"),
    auth_header: str = typer.Option("X-API-Key", help="API key header name"),
    env_name: str | None = typer.Option(None, "-e", "--env", help="Environment name (default: active)"),
    db: str = DB_OPTION,
):
    """Execute a single HTTP request."""
    _run(_run_request(url, method, header, body, body_type, auth_type,
                      auth_token, auth_user, auth_pass, auth_key, auth_header, env_name, db))


async def _run_request(url, method, headers_raw, body, body_type, auth_type,
                       auth_token, auth_user, auth_pass, auth_key, auth_header, env_name, db_path):
    async with App(db_path) as application:
        env, ctx = await _resolve_ctx(application, env_name)
        parsed_headers = _parse_headers(headers_raw)

        auth_config = {}
        if auth_type == "bearer" and auth_token:
            auth_config = {"token": auth_token}
        elif auth_type == "basic" and auth_user:
            auth_config = {"username": auth_user, "password": auth_pass or ""}
        elif auth_type == "api_key" and auth_key:
            auth_config = {"key": auth_key, "header_name": auth_header}

        request = RequestDef(
            id="cli",
            name=f"{method} {url}",
            method=HttpMethod(method.upper()),
            url=url,
            headers=parsed_headers,
            body=body,
            body_type=body_type,
            auth_type=auth_type,
            auth_config=auth_config,
        )

        hook_runner = FunctionHookRunner()
        ctx.request = request
        ctx = await hook_runner.run_pre_request(ctx)

        result, entry = await application.request_executor.execute_with_history(request, ctx)
        await application.history.save(entry)

        ctx.metadata["response"] = result
        await hook_runner.run_post_response(ctx)

        _print_response(result.status_code, result.headers, result.body, result.duration_ms, result.error)


# ──────────────────────────────────────────────────────────────────────
# BATCH
# ──────────────────────────────────────────────────────────────────────

@app.command()
def batch(
    csv_file: str = typer.Argument(help="CSV file path"),
    url: str = typer.Argument(help="Request URL (use {{column}} for variables)"),
    method: str = typer.Option("GET", "-m", "--method", help="HTTP method"),
    header: list[str] = typer.Option([], "-H", "--header", help="Headers"),
    body: str | None = typer.Option(None, "-b", "--body", help="Request body template"),
    env_name: str | None = typer.Option(None, "-e", "--env", help="Environment name"),
    save_history: bool = typer.Option(True, help="Save each request to history"),
    db: str = DB_OPTION,
):
    """Execute a request for each row in a CSV file."""
    _run(_run_batch(csv_file, url, method, header, body, env_name, save_history, db))


async def _run_batch(csv_file, url, method, headers_raw, body, env_name, save_history, db_path):
    path = Path(csv_file)
    if not path.exists():
        console.print(f"[red]CSV file not found: {csv_file}[/red]")
        raise typer.Exit(1)

    parsed_headers = _parse_headers(headers_raw)

    request = RequestDef(
        id="batch",
        name=f"{method} {url}",
        method=HttpMethod(method.upper()),
        url=url,
        headers=parsed_headers,
        body=body,
    )

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    console.print(f"Running {len(rows)} requests...")

    async with App(db_path) as application:
        env, base_ctx = await _resolve_ctx(application, env_name)
        resolver = DefaultVariableResolver()

        table = Table(title="Batch Results")
        table.add_column("Row", style="dim")
        table.add_column("Status", justify="center")
        table.add_column("Duration", justify="right")
        table.add_column("Error")

        ok = 0
        fail = 0

        for i, row in enumerate(rows, 1):
            ctx = ExecutionContext(
                environment=base_ctx.environment,
                variables=dict(base_ctx.variables),
                batch_row=dict(row),
            )
            ctx.variables = resolver.build_variable_map(ctx)

            result, entry = await application.request_executor.execute_with_history(request, ctx)

            if save_history:
                await application.history.save(entry)

            color = "green" if result.status_code < 400 else "red"
            if result.status_code < 400 and not result.error:
                ok += 1
            else:
                fail += 1
            table.add_row(
                str(i),
                f"[{color}]{result.status_code}[/{color}]",
                f"{result.duration_ms}ms",
                result.error or "",
            )

        console.print(table)
        console.print(f"\n[green]{ok} ok[/green] / [red]{fail} failed[/red]")


# ──────────────────────────────────────────────────────────────────────
# HISTORY
# ──────────────────────────────────────────────────────────────────────

history_app = typer.Typer(help="Request history commands")
app.add_typer(history_app, name="history")


@history_app.command("list")
def history_list(
    limit: int = typer.Option(20, "-n", "--limit", help="Number of entries"),
    request_id: str | None = typer.Option(None, "-r", "--request", help="Filter by request ID"),
    db: str = DB_OPTION,
):
    """Show request history."""
    _run(_show_history(limit, request_id, db))


async def _show_history(limit, request_id, db_path):
    async with App(db_path) as application:
        if request_id:
            entries = await application.history.list_by_request(request_id, limit)
        else:
            entries = await application.history.list_recent(limit)

        if not entries:
            console.print("[dim]No history entries[/dim]")
            return

        table = Table(title="Request History")
        table.add_column("ID", style="dim")
        table.add_column("Time", style="dim")
        table.add_column("Method")
        table.add_column("URL")
        table.add_column("Status", justify="center")
        table.add_column("Duration", justify="right")

        for entry in entries:
            status_color = "green" if entry["status"] == "success" else "red"
            table.add_row(
                entry["id"][:8],
                entry["created_at"][:19],
                entry["method"],
                entry["url"][:60],
                f"[{status_color}]{entry.get('status_code', 'ERR')}[/{status_color}]",
                f"{entry['duration_ms']}ms",
            )

        console.print(table)


@history_app.command("inspect")
def history_inspect(
    history_id: str = typer.Argument(help="History entry ID (or prefix)"),
    db: str = DB_OPTION,
):
    """Inspect a history entry in detail."""
    _run(_inspect_history(history_id, db))


async def _inspect_history(history_id, db_path):
    async with App(db_path) as application:
        entry = await application.history.get(history_id)
        if not entry:
            entries = await application.history.list_recent(1000)
            entry = next((e for e in entries if e["id"].startswith(history_id)), None)
        if not entry:
            console.print(f"[red]History entry '{history_id}' not found[/red]")
            raise typer.Exit(1)

        console.print(f"[bold]Request:[/bold] {entry['method']} {entry['url']}")
        console.print(f"[bold]Status:[/bold] {entry.get('status_code', 'N/A')} ({entry['status']})")
        console.print(f"[bold]Duration:[/bold] {entry['duration_ms']}ms")
        console.print(f"[bold]Time:[/bold] {entry['created_at']}")
        if entry.get("error_message"):
            console.print(f"[bold red]Error:[/bold red] {entry['error_message']}")
        if entry.get("response_body"):
            console.print("\n[bold]Response Body:[/bold]")
            try:
                parsed = json.loads(entry["response_body"])
                console.print_json(json.dumps(parsed, indent=2))
            except (json.JSONDecodeError, TypeError):
                console.print(entry["response_body"][:2000])


@history_app.command("clear")
def history_clear(
    confirm: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation"),
    db: str = DB_OPTION,
):
    """Clear all history entries."""
    _run(_clear_history(confirm, db))


async def _clear_history(confirm, db_path):
    if not confirm:
        console.print("[yellow]Use -y to confirm clearing all history[/yellow]")
        raise typer.Exit(1)
    async with App(db_path) as application:
        count = await application.history.clear()
        console.print(f"[green]Cleared {count} history entries[/green]")


# ──────────────────────────────────────────────────────────────────────
# COLLECTIONS
# ──────────────────────────────────────────────────────────────────────

collection_app = typer.Typer(help="Collection management commands")
app.add_typer(collection_app, name="collection")


@collection_app.command("list")
def collection_list(db: str = DB_OPTION):
    """List all collections."""
    _run(_list_collections(db))


async def _list_collections(db_path):
    async with App(db_path) as application:
        cols = await application.collections.list_all()
        if not cols:
            console.print("[dim]No collections[/dim]")
            return
        table = Table(title="Collections")
        table.add_column("ID", style="dim")
        table.add_column("Name")
        table.add_column("Description")
        for c in cols:
            table.add_row(c["id"][:8], c["name"], c.get("description", ""))
        console.print(table)


@collection_app.command("create")
def collection_create(
    name: str = typer.Argument(help="Collection name"),
    desc: str = typer.Option("", "-d", "--desc", help="Description"),
    db: str = DB_OPTION,
):
    """Create a new collection."""
    _run(_create_collection(name, desc, db))


async def _create_collection(name, desc, db_path):
    async with App(db_path) as application:
        col = await application.collections.create(name, desc)
        console.print(f"[green]Created collection '{name}' ({col['id'][:8]})[/green]")


@collection_app.command("delete")
def collection_delete(
    collection_id: str = typer.Argument(help="Collection ID (or prefix)"),
    db: str = DB_OPTION,
):
    """Delete a collection."""
    _run(_delete_collection(collection_id, db))


async def _delete_collection(collection_id, db_path):
    async with App(db_path) as application:
        cols = await application.collections.list_all()
        col = next((c for c in cols if c["id"].startswith(collection_id)), None)
        if not col:
            console.print(f"[red]Collection '{collection_id}' not found[/red]")
            raise typer.Exit(1)
        await application.collections.delete(col["id"])
        console.print(f"[green]Deleted collection '{col['name']}'[/green]")


@collection_app.command("add-request")
def collection_add_request(
    collection_id: str = typer.Argument(help="Collection ID (or prefix)"),
    name: str = typer.Argument(help="Request name"),
    url: str = typer.Argument(help="Request URL"),
    method: str = typer.Option("GET", "-m", "--method", help="HTTP method"),
    header: list[str] = typer.Option([], "-H", "--header", help="Headers"),
    body: str | None = typer.Option(None, "-b", "--body", help="Request body"),
    auth_type: str | None = typer.Option(None, help="Auth type"),
    auth_token: str | None = typer.Option(None, help="Auth token"),
    db: str = DB_OPTION,
):
    """Add a saved request to a collection."""
    _run(_add_request(collection_id, name, url, method, header, body, auth_type, auth_token, db))


async def _add_request(collection_id, name, url, method, headers_raw, body, auth_type, auth_token, db_path):
    async with App(db_path) as application:
        cols = await application.collections.list_all()
        col = next((c for c in cols if c["id"].startswith(collection_id)), None)
        if not col:
            console.print(f"[red]Collection '{collection_id}' not found[/red]")
            raise typer.Exit(1)

        auth_config = {}
        if auth_type == "bearer" and auth_token:
            auth_config = {"token": auth_token}

        headers = [{"key": h.split(":")[0].strip(), "value": h.split(":")[1].strip()} for h in headers_raw]

        req = await application.requests.create({
            "name": name,
            "method": method.upper(),
            "url": url,
            "headers": headers,
            "body": body,
            "auth_type": auth_type,
            "auth_config": auth_config,
            "collection_id": col["id"],
        })
        console.print(f"[green]Added request '{name}' ({req['id'][:8]}) to '{col['name']}'[/green]")


@collection_app.command("requests")
def collection_requests(
    collection_id: str = typer.Argument(help="Collection ID (or prefix)"),
    db: str = DB_OPTION,
):
    """List requests in a collection."""
    _run(_list_requests(collection_id, db))


async def _list_requests(collection_id, db_path):
    async with App(db_path) as application:
        cols = await application.collections.list_all()
        col = next((c for c in cols if c["id"].startswith(collection_id)), None)
        if not col:
            console.print(f"[red]Collection '{collection_id}' not found[/red]")
            raise typer.Exit(1)

        reqs = await application.requests.list_all(col["id"])
        if not reqs:
            console.print(f"[dim]No requests in '{col['name']}'[/dim]")
            return

        table = Table(title=f"Requests in {col['name']}")
        table.add_column("ID", style="dim")
        table.add_column("Name")
        table.add_column("Method")
        table.add_column("URL")
        for r in reqs:
            table.add_row(r["id"][:8], r["name"], r["method"], r["url"][:60])
        console.print(table)


@collection_app.command("run")
def collection_run(
    request_id: str = typer.Argument(help="Request ID (or prefix)"),
    env_name: str | None = typer.Option(None, "-e", "--env", help="Environment name"),
    db: str = DB_OPTION,
):
    """Execute a saved request by ID."""
    _run(_run_saved_request(request_id, env_name, db))


async def _run_saved_request(request_id, env_name, db_path):
    async with App(db_path) as application:
        reqs = await application.requests.list_all()
        req_data = next((r for r in reqs if r["id"].startswith(request_id)), None)
        if not req_data:
            console.print(f"[red]Request '{request_id}' not found[/red]")
            raise typer.Exit(1)

        env, ctx = await _resolve_ctx(application, env_name)
        ctx.request = RequestDef(
            id=req_data["id"],
            name=req_data["name"],
            method=HttpMethod(req_data["method"]),
            url=req_data["url"],
            headers=[RequestParam(key=h["key"], value=h["value"]) for h in json.loads(req_data.get("headers", "[]"))],
            body=req_data.get("body"),
            body_type=req_data.get("body_type"),
            auth_type=req_data.get("auth_type"),
            auth_config=json.loads(req_data.get("auth_config", "{}")),
        )

        hook_runner = FunctionHookRunner()
        ctx = await hook_runner.run_pre_request(ctx)

        result, entry = await application.request_executor.execute_with_history(ctx.request, ctx)
        await application.history.save(entry)

        ctx.metadata["response"] = result
        await hook_runner.run_post_response(ctx)

        _print_response(result.status_code, result.headers, result.body, result.duration_ms, result.error)


# ──────────────────────────────────────────────────────────────────────
# ENVIRONMENTS
# ──────────────────────────────────────────────────────────────────────

env_app = typer.Typer(help="Environment management commands")
app.add_typer(env_app, name="env")


@env_app.command("list")
def env_list(db: str = DB_OPTION):
    """List all environments."""
    _run(_env_list(db))


async def _env_list(db_path):
    async with App(db_path) as application:
        envs = await application.environments.list_all()
        if not envs:
            console.print("[dim]No environments[/dim]")
            return
        table = Table(title="Environments")
        table.add_column("ID", style="dim")
        table.add_column("Name")
        table.add_column("Active", justify="center")
        table.add_column("Variables", justify="right")
        for e in envs:
            active = "[green]yes[/green]" if e["is_active"] else "no"
            var_count = len(e.get("variables", []))
            table.add_row(e["id"][:8], e["name"], active, str(var_count))
        console.print(table)


@env_app.command("create")
def env_create(
    name: str = typer.Argument(help="Environment name"),
    db: str = DB_OPTION,
):
    """Create a new environment."""
    _run(_env_create(name, db))


async def _env_create(name, db_path):
    async with App(db_path) as application:
        env = await application.environments.create(name)
        console.print(f"[green]Created environment '{name}' ({env['id'][:8]})[/green]")


@env_app.command("delete")
def env_delete(
    name: str = typer.Argument(help="Environment name"),
    db: str = DB_OPTION,
):
    """Delete an environment."""
    _run(_env_delete(name, db))


async def _env_delete(name, db_path):
    async with App(db_path) as application:
        envs = await application.environments.list_all()
        env = next((e for e in envs if e["name"] == name), None)
        if not env:
            console.print(f"[red]Environment '{name}' not found[/red]")
            raise typer.Exit(1)
        await application.environments.delete(env["id"])
        console.print(f"[green]Deleted environment '{name}'[/green]")


@env_app.command("activate")
def env_activate(
    name: str = typer.Argument(help="Environment name"),
    db: str = DB_OPTION,
):
    """Activate an environment."""
    _run(_env_activate(name, db))


async def _env_activate(name, db_path):
    async with App(db_path) as application:
        envs = await application.environments.list_all()
        env = next((e for e in envs if e["name"] == name), None)
        if not env:
            console.print(f"[red]Environment '{name}' not found[/red]")
            raise typer.Exit(1)
        await application.environments.set_active(env["id"])
        console.print(f"[green]Activated environment '{name}'[/green]")


@env_app.command("set-var")
def env_set_var(
    name: str = typer.Argument(help="Environment name"),
    key_value: str = typer.Argument(help="Variable as KEY=VALUE"),
    secret: bool = typer.Option(False, "-s", "--secret", help="Mark as secret"),
    db: str = DB_OPTION,
):
    """Set a variable in an environment."""
    _run(_env_set_var(name, key_value, secret, db))


async def _env_set_var(name, key_value, secret, db_path):
    key, _, value = key_value.partition("=")
    if not key or not value:
        console.print("[red]Format: KEY=VALUE[/red]")
        raise typer.Exit(1)
    async with App(db_path) as application:
        envs = await application.environments.list_all()
        env = next((e for e in envs if e["name"] == name), None)
        if not env:
            console.print(f"[red]Environment '{name}' not found[/red]")
            raise typer.Exit(1)
        await application.environments.set_variable(env["id"], key.strip(), value.strip(), is_secret=secret)
        console.print(f"[green]Set {key.strip()} in '{name}'[/green]")


@env_app.command("delete-var")
def env_delete_var(
    name: str = typer.Argument(help="Environment name"),
    key: str = typer.Argument(help="Variable key"),
    db: str = DB_OPTION,
):
    """Delete a variable from an environment."""
    _run(_env_delete_var(name, key, db))


async def _env_delete_var(name, key, db_path):
    async with App(db_path) as application:
        envs = await application.environments.list_all()
        env = next((e for e in envs if e["name"] == name), None)
        if not env:
            console.print(f"[red]Environment '{name}' not found[/red]")
            raise typer.Exit(1)
        deleted = await application.environments.delete_variable(env["id"], key)
        if deleted:
            console.print(f"[green]Deleted variable '{key}' from '{name}'[/green]")
        else:
            console.print(f"[yellow]Variable '{key}' not found in '{name}'[/yellow]")


@env_app.command("vars")
def env_vars(
    name: str = typer.Argument(help="Environment name"),
    db: str = DB_OPTION,
):
    """List variables in an environment."""
    _run(_env_vars(name, db))


async def _env_vars(name, db_path):
    async with App(db_path) as application:
        envs = await application.environments.list_all()
        env = next((e for e in envs if e["name"] == name), None)
        if not env:
            console.print(f"[red]Environment '{name}' not found[/red]")
            raise typer.Exit(1)

        variables = env.get("variables", [])
        if not variables:
            console.print(f"[dim]No variables in '{name}'[/dim]")
            return

        table = Table(title=f"Variables in {name}")
        table.add_column("Key")
        table.add_column("Value")
        table.add_column("Secret", justify="center")
        for v in variables:
            val = "****" if v.get("is_secret") else v["value"]
            secret = "[yellow]yes[/yellow]" if v.get("is_secret") else "no"
            table.add_row(v["key"], val, secret)
        console.print(table)


# ──────────────────────────────────────────────────────────────────────
# EXPORT
# ──────────────────────────────────────────────────────────────────────

@app.command()
def export(
    format: str = typer.Option("json", "-f", "--format", help="Export format: json, csv"),
    output: str = typer.Option("export.json", "-o", "--output", help="Output file path"),
    limit: int = typer.Option(100, "-n", "--limit", help="Max entries to export"),
    db: str = DB_OPTION,
):
    """Export request history to JSON or CSV."""
    _run(_run_export(format, output, limit, db))


async def _run_export(format, output, limit, db_path):
    async with App(db_path) as application:
        entries = await application.history.list_recent(limit)
        if not entries:
            console.print("[dim]No history to export[/dim]")
            return

        if format == "json":
            result = await application.export_pipeline.export_json(entries, output)
        elif format == "csv":
            result = await application.export_pipeline.export_csv(entries, output)
        else:
            console.print(f"[red]Unknown format: {format}[/red]")
            raise typer.Exit(1)

        console.print(f"[green]Exported {result.record_count} records to {output}[/green]")


# ──────────────────────────────────────────────────────────────────────
# WORKFLOW
# ──────────────────────────────────────────────────────────────────────

@app.command()
def workflow(
    file: str = typer.Argument(help="Workflow JSON file path"),
    env_name: str | None = typer.Option(None, "-e", "--env", help="Environment name"),
    save_history: bool = typer.Option(True, help="Save step history"),
    db: str = DB_OPTION,
):
    """Execute a workflow from a JSON definition file."""
    _run(_run_workflow(file, env_name, save_history, db))


async def _run_workflow(file, env_name, save_history, db_path):
    path = Path(file)
    if not path.exists():
        console.print(f"[red]Workflow file not found: {file}[/red]")
        raise typer.Exit(1)

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    steps = []
    for s in data.get("steps", []):
        steps.append(WorkflowStep(
            id=s["id"],
            name=s.get("name", s["id"]),
            step_type=StepType(s["type"]),
            request_id=s.get("request_id"),
            function_name=s.get("function_name"),
            config=s.get("config", {}),
            depends_on=s.get("depends_on", []),
            condition=s.get("condition"),
            output_variable=s.get("output_variable"),
            retry=RetryConfig(
                max_retries=s.get("retry", {}).get("max_retries", 0),
                delay_ms=s.get("retry", {}).get("delay_ms", 1000),
                strategy=RetryStrategy(s.get("retry", {}).get("strategy", "fixed")),
            ),
        ))

    workflow_def = WorkflowDef(
        id=data.get("id", "cli-workflow"),
        name=data.get("name", "CLI Workflow"),
        description=data.get("description", ""),
        steps=steps,
        variables=data.get("variables", {}),
    )

    async with App(db_path) as application:
        from app.core.engine.workflow import WorkflowEngine

        engine = WorkflowEngine(
            request_executor=application.request_executor,
            event_bus=application.event_bus,
        )

        requests_map: dict = {}
        for s in steps:
            if s.request_id:
                req_data = await application.requests.get(s.request_id)
                if req_data:
                    headers = []
                    for h in json.loads(req_data.get("headers", "[]")):
                        headers.append(RequestParam(key=h["key"], value=h["value"]))
                    requests_map[s.request_id] = RequestDef(
                        id=req_data["id"],
                        name=req_data["name"],
                        method=HttpMethod(req_data["method"]),
                        url=req_data["url"],
                        headers=headers,
                        body=req_data.get("body"),
                        auth_type=req_data.get("auth_type"),
                        auth_config=json.loads(req_data.get("auth_config", "{}")),
                    )

        env, ctx = await _resolve_ctx(application, env_name)

        console.print(f"Running workflow: [bold]{workflow_def.name}[/bold]")
        result = await engine.execute(workflow_def, ctx, requests_map)

        if save_history:
            for entry in result.history_entries:
                await application.history.save(entry)

        table = Table(title=f"Workflow: {result.workflow_name}")
        table.add_column("Step")
        table.add_column("Status", justify="center")
        table.add_column("Duration", justify="right")
        table.add_column("Details")

        for sr in result.step_results:
            status = "[green]OK[/green]" if sr.success else "[red]FAIL[/red]"
            detail = sr.error or (str(sr.output)[:50] if sr.output else "")
            table.add_row(sr.step_name, status, f"{sr.duration_ms}ms", detail)

        console.print(table)
        color = "green" if result.success else "red"
        console.print(f"\n[{color}]{'PASSED' if result.success else 'FAILED'}[/{color}] {result.total_duration_ms}ms")


# ──────────────────────────────────────────────────────────────────────
# FUNCTIONS
# ──────────────────────────────────────────────────────────────────────

@app.command()
def functions(
    dir: str = typer.Option("functions", "-d", "--dir", help="Functions directory"),
    include_plugins: bool = typer.Option(True, help="Include plugin functions"),
    plugins_dir: str = typer.Option("plugins", help="Plugins directory"),
):
    """List discovered Python functions."""
    from app.core.engine.function_runner import FilesystemFunctionRunner
    from app.core.engine.plugin_registry import FilesystemPluginRegistry

    runner = FilesystemFunctionRunner(dir)
    funcs = runner.discover()

    if include_plugins:
        registry = FilesystemPluginRegistry(plugins_dir)
        registry.discover()
        for info in registry.list_plugins():
            if info.status != PluginStatus.ERROR:
                try:
                    registry.load(info.manifest.name)
                except Exception:
                    pass
        plugin_funcs = registry.get_all_functions()
        for f in plugin_funcs:
            f["_source"] = f"plugin:{f.get('plugin', '?')}"
        funcs.extend(plugin_funcs)

    if not funcs:
        console.print("[dim]No functions discovered[/dim]")
        return

    table = Table(title="Discovered Functions")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Version")
    table.add_column("Source")
    table.add_column("Path", style="dim")

    for f in funcs:
        source = f.get("_source", "local")
        table.add_row(
            f.get("name", "?"),
            f.get("type", "?"),
            f.get("version", "?"),
            source,
            f.get("path", "?"),
        )
    console.print(table)


# ──────────────────────────────────────────────────────────────────────
# PLUGINS
# ──────────────────────────────────────────────────────────────────────

plugin_app = typer.Typer(help="Plugin management commands")
app.add_typer(plugin_app, name="plugins")


@plugin_app.command("list")
def plugins_list(
    plugins_dir: str = typer.Option("plugins", "-d", "--dir", help="Plugins directory"),
):
    """List all discovered plugins."""
    from app.core.engine.plugin_registry import FilesystemPluginRegistry

    registry = FilesystemPluginRegistry(plugins_dir)
    plugins = registry.discover()

    if not plugins:
        console.print("[dim]No plugins discovered[/dim]")
        return

    table = Table(title="Plugins")
    table.add_column("Name")
    table.add_column("Version")
    table.add_column("Status")
    table.add_column("Description")
    table.add_column("Functions", justify="right")
    table.add_column("Workflows", justify="right")

    for info in plugins:
        status_color = {
            PluginStatus.ACTIVE: "green",
            PluginStatus.LOADED: "yellow",
            PluginStatus.DISCOVERED: "dim",
            PluginStatus.ERROR: "red",
        }.get(info.status, "dim")

        table.add_row(
            info.manifest.name,
            info.manifest.version,
            f"[{status_color}]{info.status}[/{status_color}]",
            info.manifest.description[:40],
            str(len(info.manifest.functions)),
            str(len(info.manifest.workflows)),
        )

    console.print(table)


@plugin_app.command("info")
def plugins_info(
    name: str = typer.Argument(help="Plugin name"),
    plugins_dir: str = typer.Option("plugins", "-d", "--dir", help="Plugins directory"),
):
    """Show detailed information about a plugin."""
    from app.core.engine.plugin_registry import FilesystemPluginRegistry

    registry = FilesystemPluginRegistry(plugins_dir)
    registry.discover()

    try:
        info = registry.load(name)
    except Exception as exc:
        console.print(f"[red]Failed to load plugin '{name}': {exc}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]{info.manifest.name}[/bold] v{info.manifest.version}")
    if info.manifest.description:
        console.print(f"  {info.manifest.description}")
    if info.manifest.author:
        console.print(f"  Author: {info.manifest.author}")
    console.print(f"  Status: [{ 'green' if info.status == PluginStatus.ACTIVE else 'dim'}]{info.status}[/]")
    console.print(f"  Path: {info.manifest.path}")

    if info.manifest.variables:
        console.print("\n[bold]Variables:[/bold]")
        for k, v in info.manifest.variables.items():
            console.print(f"  {k} = {v}")

    if info.manifest.hooks:
        console.print("\n[bold]Hooks:[/bold]")
        for hook_type, hook_path in info.manifest.hooks.items():
            console.print(f"  {hook_type}: {hook_path}")

    if info.manifest.dependencies:
        console.print(f"\n[bold]Dependencies:[/bold] {', '.join(info.manifest.dependencies)}")

    if info.functions:
        console.print("\n[bold]Functions:[/bold]")
        func_table = Table(show_header=True)
        func_table.add_column("Name")
        func_table.add_column("Type")
        func_table.add_column("Description")
        for f in info.functions:
            func_table.add_row(f.get("name", "?"), f.get("type", "?"), f.get("description", ""))
        console.print(func_table)

    if info.workflows:
        console.print("\n[bold]Workflows:[/bold]")
        for wf in info.workflows:
            console.print(f"  {wf.get('name', '?')} ({wf.get('id', '?')})")

    if info.error:
        console.print(f"\n[red]Error: {info.error}[/red]")


@plugin_app.command("create")
def plugins_create(
    name: str = typer.Argument(help="Plugin name (kebab-case)"),
    plugins_dir: str = typer.Option("plugins", "-d", "--dir", help="Plugins directory"),
):
    """Scaffold a new plugin directory."""
    from app.core.engine.plugin_registry import FilesystemPluginRegistry

    registry = FilesystemPluginRegistry(plugins_dir)

    if (registry._base / name).exists():
        console.print(f"[red]Plugin '{name}' already exists[/red]")
        raise typer.Exit(1)

    plugin_dir = registry.scaffold_plugin(name)
    console.print(f"[green]Created plugin '{name}' at {plugin_dir}[/green]")
    console.print("\nFiles created:")
    for p in sorted(plugin_dir.rglob("*")):
        if p.is_file():
            console.print(f"  {p.relative_to(plugin_dir)}")


@plugin_app.command("reload")
def plugins_reload(
    plugins_dir: str = typer.Option("plugins", "-d", "--dir", help="Plugins directory"),
):
    """Re-scan and reload all plugins."""
    from app.core.engine.plugin_registry import FilesystemPluginRegistry

    registry = FilesystemPluginRegistry(plugins_dir)
    plugins = registry.reload()

    loaded = sum(1 for p in plugins if p.status == PluginStatus.ACTIVE)
    errors = sum(1 for p in plugins if p.status == PluginStatus.ERROR)
    console.print(f"[green]Reloaded {len(plugins)} plugins ({loaded} active, {errors} errors)[/green]")


# ──────────────────────────────────────────────────────────────────────
# TUI
# ──────────────────────────────────────────────────────────────────────

@app.command()
def tui(
    db: str = DB_OPTION,
):
    """Launch the interactive Terminal User Interface."""
    from app.ui.tui import launch_tui

    launch_tui(db)


# ──────────────────────────────────────────────────────────────────────
# FULL EXPORT / IMPORT
# ──────────────────────────────────────────────────────────────────────

@app.command()
def export_all(
    output_dir: str = typer.Argument(help="Output directory for full export"),
    db: str = DB_OPTION,
):
    """Export all SCLPLAPI data (workflows, functions, history, etc.)."""
    _run(_run_export_all(output_dir, db))


async def _run_export_all(output_dir, db_path):
    from app.services.full_export_service import FullExportService

    async with App(db_path) as application:
        exporter = FullExportService(application.db)
        base = await exporter.export_all(output_dir)
        console.print(f"[green]Full export complete: {base}[/green]")


@app.command()
def import_all(
    export_dir: str = typer.Argument(help="Export directory to import from"),
    db: str = DB_OPTION,
):
    """Import all SCLPLAPI data from an export directory."""
    _run(_run_import_all(export_dir, db))


async def _run_import_all(export_dir, db_path):
    from app.services.full_import_service import FullImportService

    async with App(db_path) as application:
        importer = FullImportService(application.db)
        result = await importer.import_all(export_dir)
        for section, count in result.items():
            console.print(f"  {section}: {count}")
        console.print("[green]Full import complete[/green]")


export_app = typer.Typer(help="Selective export commands")
app.add_typer(export_app, name="export-selective")


@export_app.command("workflows")
def export_workflows(
    output_dir: str = typer.Argument(help="Output directory"),
    db: str = DB_OPTION,
):
    """Export all workflows."""
    _run(_run_selective_export("workflows", output_dir, db))


@export_app.command("functions")
def export_functions(
    output_dir: str = typer.Argument(help="Output directory"),
    db: str = DB_OPTION,
):
    """Export all function files."""
    _run(_run_selective_export("functions", output_dir, db))


@export_app.command("history")
def export_history(
    output_dir: str = typer.Argument(help="Output directory"),
    db: str = DB_OPTION,
):
    """Export execution history."""
    _run(_run_selective_export("history", output_dir, db))


@export_app.command("environments")
def export_environments(
    output_dir: str = typer.Argument(help="Output directory"),
    db: str = DB_OPTION,
):
    """Export environments and variables."""
    _run(_run_selective_export("environments", output_dir, db))


@export_app.command("collections")
def export_collections(
    output_dir: str = typer.Argument(help="Output directory"),
    db: str = DB_OPTION,
):
    """Export collections and requests."""
    _run(_run_selective_export("collections", output_dir, db))


async def _run_selective_export(section, output_dir, db_path):
    from app.services.full_export_service import FullExportService

    async with App(db_path) as application:
        exporter = FullExportService(application.db)
        method = getattr(exporter, f"export_{section}", None)
        if not method:
            console.print(f"[red]Unknown section: {section}[/red]")
            raise typer.Exit(1)
        count = await method(Path(output_dir) / section)
        console.print(f"[green]Exported {section}: {count} items[/green]")

