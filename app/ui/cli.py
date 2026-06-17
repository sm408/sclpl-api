from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from app.core.engine.hooks import FunctionHookRunner
from app.core.engine.variable_resolver import DefaultVariableResolver
from app.core.models.context import ExecutionContext
from app.core.models.environment import Environment, Variable, VariableScope
from app.core.models.request import HttpMethod, RequestDef, RequestParam
from app.core.models.workflow import WorkflowDef, WorkflowStep, StepType, RetryConfig
from app.ui.app import App

app = typer.Typer(
    name="sclplapi",
    help="Local-first, Python-first API workflow studio",
    no_args_is_help=True,
)
console = Console()


def _run(coro):
    return asyncio.run(coro)


@app.command()
def run(
    url: str = typer.Argument(help="Request URL"),
    method: str = typer.Option("GET", "-m", "--method", help="HTTP method"),
    header: list[str] = typer.Option([], "-H", "--header", help="Headers (Key: Value)"),
    body: str | None = typer.Option(None, "-b", "--body", help="Request body"),
    env_name: str | None = typer.Option(None, "-e", "--env", help="Environment name"),
    db_path: str = typer.Option("data/sclplapi.db", help="Database path"),
):
    """Execute a single HTTP request."""
    _run(_run_request(url, method, header, body, env_name, db_path))


async def _run_request(url, method, headers_raw, body, env_name, db_path):
    async with App(db_path) as application:
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

        parsed_headers = []
        for h in headers_raw:
            key, _, value = h.partition(":")
            parsed_headers.append(RequestParam(key=key.strip(), value=value.strip()))

        request = RequestDef(
            id="cli",
            name=f"{method} {url}",
            method=HttpMethod(method.upper()),
            url=url,
            headers=parsed_headers,
            body=body,
        )

        resolver = DefaultVariableResolver()
        ctx = ExecutionContext(
            environment=_dict_to_env(env) if env else None,
            variables=variables,
        )
        ctx.variables = resolver.build_variable_map(ctx)

        hook_runner = FunctionHookRunner()
        ctx = await hook_runner.run_pre_request(ctx)

        result, entry = await application.request_executor.execute_with_history(request, ctx)
        await application.history.save(entry)

        ctx.metadata["response"] = result
        await hook_runner.run_post_response(ctx)

        _print_response(result.status_code, result.headers, result.body, result.duration_ms, result.error)


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


@app.command()
def batch(
    csv_file: str = typer.Argument(help="CSV file path"),
    url: str = typer.Argument(help="Request URL (use {{column}} for variables)"),
    method: str = typer.Option("GET", "-m", "--method", help="HTTP method"),
    header: list[str] = typer.Option([], "-H", "--header", help="Headers"),
    body: str | None = typer.Option(None, "-b", "--body", help="Request body template"),
    db_path: str = typer.Option("data/sclplapi.db", help="Database path"),
):
    """Execute a request for each row in a CSV file."""
    _run(_run_batch(csv_file, url, method, header, body, db_path))


async def _run_batch(csv_file, url, method, headers_raw, body, db_path):
    import csv as csv_mod

    path = Path(csv_file)
    if not path.exists():
        console.print(f"[red]CSV file not found: {csv_file}[/red]")
        raise typer.Exit(1)

    parsed_headers = []
    for h in headers_raw:
        key, _, value = h.partition(":")
        parsed_headers.append(RequestParam(key=key.strip(), value=value.strip()))

    request = RequestDef(
        id="batch",
        name=f"{method} {url}",
        method=HttpMethod(method.upper()),
        url=url,
        headers=parsed_headers,
        body=body,
    )

    with open(path, encoding="utf-8") as f:
        reader = csv_mod.DictReader(f)
        rows = list(reader)

    console.print(f"Running {len(rows)} requests...")

    async with App(db_path) as application:
        resolver = DefaultVariableResolver()
        table = Table(title="Batch Results")
        table.add_column("Row", style="dim")
        table.add_column("Status", justify="center")
        table.add_column("Duration", justify="right")
        table.add_column("Error")

        for i, row in enumerate(rows, 1):
            ctx = ExecutionContext(batch_row=dict(row))
            ctx.variables = resolver.build_variable_map(ctx)

            result = await application.request_executor.execute(request, ctx)
            color = "green" if result.status_code < 400 else "red"
            table.add_row(
                str(i),
                f"[{color}]{result.status_code}[/{color}]",
                f"{result.duration_ms}ms",
                result.error or "",
            )

        console.print(table)


@app.command()
def history(
    limit: int = typer.Option(20, "-n", "--limit", help="Number of entries"),
    db_path: str = typer.Option("data/sclplapi.db", help="Database path"),
):
    """Show request history."""
    _run(_show_history(limit, db_path))


async def _show_history(limit, db_path):
    async with App(db_path) as application:
        entries = await application.history.list_recent(limit)
        if not entries:
            console.print("[dim]No history entries[/dim]")
            return

        table = Table(title="Request History")
        table.add_column("Time", style="dim")
        table.add_column("Method")
        table.add_column("URL")
        table.add_column("Status", justify="center")
        table.add_column("Duration", justify="right")

        for entry in entries:
            status_color = "green" if entry["status"] == "success" else "red"
            table.add_row(
                entry["created_at"][:19],
                entry["method"],
                entry["url"][:60],
                f"[{status_color}]{entry.get('status_code', 'ERR')}[/{status_color}]",
                f"{entry['duration_ms']}ms",
            )

        console.print(table)


@app.command()
def collections(
    db_path: str = typer.Option("data/sclplapi.db", help="Database path"),
):
    """List all collections."""
    _run(_list_collections(db_path))


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


@app.command("env")
def env_cmd(
    action: str = typer.Argument(help="Action: list, create, set-var, activate"),
    name: str | None = typer.Argument(None, help="Environment name or key"),
    value: str | None = typer.Argument(None, help="Variable value"),
    db_path: str = typer.Option("data/sclplapi.db", help="Database path"),
):
    """Manage environments: list, create, set-var, activate."""
    _run(_manage_env(action, name, value, db_path))


async def _manage_env(action, name, value, db_path):
    async with App(db_path) as application:
        if action == "list":
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
                table.add_row(e["id"][:8], e["name"], active, str(len(e.get("variables", []))))
            console.print(table)

        elif action == "create":
            if not name:
                console.print("[red]Environment name required[/red]")
                raise typer.Exit(1)
            env = await application.environments.create(name)
            console.print(f"[green]Created environment '{name}' ({env['id'][:8]})[/green]")

        elif action == "set-var":
            if not name or not value:
                console.print("[red]Usage: env set-var <env_name> KEY=VALUE[/red]")
                raise typer.Exit(1)
            envs = await application.environments.list_all()
            env = next((e for e in envs if e["name"] == name), None)
            if not env:
                console.print(f"[red]Environment '{name}' not found[/red]")
                raise typer.Exit(1)
            key, _, val = value.partition("=")
            await application.environments.set_variable(env["id"], key.strip(), val.strip())
            console.print(f"[green]Set {key.strip()} in '{name}'[/green]")

        elif action == "activate":
            if not name:
                console.print("[red]Environment name required[/red]")
                raise typer.Exit(1)
            envs = await application.environments.list_all()
            env = next((e for e in envs if e["name"] == name), None)
            if not env:
                console.print(f"[red]Environment '{name}' not found[/red]")
                raise typer.Exit(1)
            await application.environments.set_active(env["id"])
            console.print(f"[green]Activated environment '{name}'[/green]")


@app.command()
def export(
    format: str = typer.Option("json", "-f", "--format", help="Export format: json, csv"),
    output: str = typer.Option("export.json", "-o", "--output", help="Output file path"),
    limit: int = typer.Option(100, "-n", "--limit", help="Max entries to export"),
    db_path: str = typer.Option("data/sclplapi.db", help="Database path"),
):
    """Export request history to JSON or CSV."""
    _run(_run_export(format, output, limit, db_path))


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


@app.command()
def workflow(
    file: str = typer.Argument(help="Workflow JSON file path"),
    db_path: str = typer.Option("data/sclplapi.db", help="Database path"),
):
    """Execute a workflow from a JSON definition file."""
    _run(_run_workflow(file, db_path))


async def _run_workflow(file, db_path):
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

        requests: dict = {}
        for s in steps:
            if s.request_id:
                req_data = await application.requests.get(s.request_id)
                if req_data:
                    requests[s.request_id] = RequestDef(
                        id=req_data["id"],
                        name=req_data["name"],
                        method=HttpMethod(req_data["method"]),
                        url=req_data["url"],
                    )

        env = await application.environments.get_active()
        variables: dict[str, str] = {}
        if env:
            for v in env.get("variables", []):
                variables[v["key"]] = v["value"]

        ctx = ExecutionContext(
            environment=_dict_to_env(env) if env else None,
            variables=variables,
        )

        console.print(f"Running workflow: {workflow_def.name}")
        result = await engine.execute(workflow_def, ctx, requests)

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


@app.command()
def functions(
    db_path: str = typer.Option("data/sclplapi.db", help="Functions directory"),
    dir: str = typer.Option("functions", "-d", "--dir", help="Functions directory"),
):
    """List discovered Python functions."""
    from app.core.engine.function_runner import FilesystemFunctionRunner

    runner = FilesystemFunctionRunner(dir)
    funcs = runner.discover()

    if not funcs:
        console.print("[dim]No functions discovered[/dim]")
        return

    table = Table(title="Discovered Functions")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Version")
    table.add_column("Path", style="dim")

    for f in funcs:
        table.add_row(
            f.get("name", "?"),
            f.get("type", "?"),
            f.get("version", "?"),
            f.get("path", "?"),
        )

    console.print(table)
