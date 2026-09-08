"""`sclpl runs`, `sclpl secret`, `sclpl doctor`, `sclpl completion`.

The commands that are about the *tool* rather than about a workflow.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from sclpl.errors import EXIT_USAGE, ValidationError
from sclpl.state import db, secrets

runs_app = typer.Typer(no_args_is_help=True, help="What has been run, and what it did.")
secret_app = typer.Typer(no_args_is_help=True, help="Credentials, kept in the OS keyring.")


def register(root: typer.Typer) -> None:
    root.add_typer(runs_app, name="runs")
    root.add_typer(secret_app, name="secret")
    root.command("doctor", help="Check the installation and say what is missing.")(doctor)
    root.command("completion", help="Print a shell completion script.")(completion)


RunArg = Annotated[str, typer.Argument(help="Run id or name; a unique prefix will do.")]
EnvOpt = Annotated[str, typer.Option("--env", help="Which environment.")]


# -- runs ---------------------------------------------------------------------------


@runs_app.command("list")
def runs_list(
    limit: Annotated[int, typer.Option("--limit", "-n", help="How many.")] = 20,
    workflow: Annotated[str | None, typer.Option("--workflow", help="Only this workflow.")] = None,
) -> None:
    """The most recent runs, newest first."""
    with db.History() as history:
        rows = history.recent(limit, workflow=workflow)
        if not rows:
            typer.echo("no runs recorded yet", err=True)
            return
        typer.echo(f"{'id':<10} {'name':<28} {'status':<10} {'ms':>7}  tags")
        typer.echo(f"{'-' * 10} {'-' * 28} {'-' * 10} {'-' * 7}  ----")
        for row in rows:
            pin = "*" if row["pinned"] else " "
            tags = ", ".join(history.tags_of(row["id"]))
            typer.echo(
                f"{pin}{row['id']:<9} {row['name'][:28]:<28} {row['status']:<10} "
                f"{row['duration_ms'] or 0:>7}  {tags}"
            )


@runs_app.command()
def show(run: RunArg) -> None:
    """One run: what it did, step by step."""
    with db.History() as history:
        row = history.find(run)
        typer.echo(f"{row['name']}  [{row['id']}]")
        typer.echo(f"  workflow   {row['workflow']} v{row['workflow_version']}")
        if row["mode"]:
            typer.echo(f"  mode       {row['mode']}")
        typer.echo(f"  status     {row['status']} (exit {row['exit_code']})")
        typer.echo(f"  started    {row['started_at']}")
        typer.echo(f"  duration   {row['duration_ms']}ms")
        typer.echo(
            f"  steps      {row['steps_run']} ok, {row['steps_failed']} failed, "
            f"{row['steps_skipped']} skipped"
        )
        if row["cache_hits"] or row["cache_misses"]:
            typer.echo(f"  cache      {row['cache_hits']} hit / {row['cache_misses']} miss")
        tags = history.tags_of(row["id"])
        if tags:
            typer.echo(f"  tags       {', '.join(tags)}")
        if row["log_path"]:
            typer.echo(f"  log        {row['log_path']}")

        ports = history.ports_of(row["id"])
        if ports:
            typer.echo("\n  ports")
            for port in ports:
                typer.echo(f"    {port['direction']:<4} {port['name']:<16} {port['path']}")

        steps = history.steps_of(row["id"])
        if steps:
            typer.echo("\n  steps")
            for step in steps:
                mark = {"ok": " ", "failed": "!", "skipped": "-"}.get(step["status"], "?")
                typer.echo(f"  {mark} {step['step_id']:<28} {step['status']}")
                if step["error"]:
                    typer.echo(f"      {step['error'].splitlines()[0]}")


@runs_app.command()
def search(
    text: Annotated[str, typer.Argument(help="Matched against names, tags, and errors.")],
    limit: Annotated[int, typer.Option("--limit", "-n")] = 20,
) -> None:
    """Find a run by anything it recorded — including the error it failed with."""
    with db.History() as history:
        rows = history.search(text, limit=limit)
        if not rows:
            typer.echo(f"nothing matching {text!r}", err=True)
            raise typer.Exit(EXIT_USAGE)
        for row in rows:
            typer.echo(f"{row['id']:<10} {row['name']:<28} {row['status']}")


@runs_app.command("report")
def runs_report(
    run: RunArg,
    fmt: Annotated[str, typer.Option("--format", help="text, json, or html.")] = "text",
    into: Annotated[Path | None, typer.Option("--into", help="Write here instead.")] = None,
) -> None:
    """A summary of one run. Unmeasured fields show as unknown, never a fake zero."""
    from typing import cast

    from sclpl.render.report import Format, render

    if fmt not in ("text", "json", "html"):
        raise ValidationError(f"unknown --format {fmt!r}", remedies=["one of: text, json, html"])
    with db.History() as history:
        row = history.find(run)
        payload = render(
            cast(Format, fmt), row, history.steps_of(row["id"]), history.tags_of(row["id"])
        )
    if into is None:
        sys.stdout.write(payload if payload.endswith("\n") else payload + "\n")
    else:
        into.write_text(payload, encoding="utf-8")
        typer.echo(f"wrote {into}", err=True)


@runs_app.command("diff")
def runs_diff(left: RunArg, right: RunArg) -> None:
    """What changed between two runs."""
    with db.History() as history:
        first, second = history.find(left), history.find(right)
        typer.echo(f"{first['name']}  ->  {second['name']}")
        if not db.compatible(first, second):
            typer.echo(
                "  note: different workflow or environment -- this comparison may not mean much",
                err=True,
            )
        lines = db.diff(first, second)
        if not lines:
            typer.echo("  no differences in what was recorded")
            return
        for line in lines:
            typer.echo(line)


@runs_app.command()
def replay(run: RunArg) -> None:
    """Print the command that would repeat a run.

    Printed rather than executed. A replay is usually wanted *with a change* -- a
    different mode, a fresh cache, one more page -- and a command you can edit is more
    use than one that has already gone.
    """
    with db.History() as history:
        row = history.find(run)
        if not row["argv"]:
            raise ValidationError(
                f"run {row['id']} did not record its command line",
                remedies=["`runs show` has what it did"],
            )
        typer.echo(f"  sclpl {row['argv']}")


@runs_app.command("which")
def runs_which(path: Annotated[Path, typer.Argument(help="An output file to trace.")]) -> None:
    """F3: which run(s) produced this file, and whether it has changed since."""
    with db.History() as history:
        matches = history.producers_of(path)
        if not matches:
            typer.echo(f"no recorded run produced {path}", err=True)
            raise typer.Exit(EXIT_USAGE)
        if len(matches) > 1:
            typer.echo(f"ambiguous: {len(matches)} runs recorded producing this path", err=True)
        current = db.file_digest(path)
        for row in matches:
            typer.echo(f"{row['run_name']}  [{row['run_id']}]  {row['started_at']}")
            if not current:
                typer.echo("  file no longer exists", err=True)
            elif row["digest"] and row["digest"] != current:
                typer.echo("  modified since this run: current content does not match", err=True)


@runs_app.command("resume-plan")
def runs_resume_plan(
    run: RunArg,
    workflow: Annotated[str, typer.Argument(help="Workflow name or path to resume.")],
    mode: Annotated[str | None, typer.Option("--mode", "-m", help="Named subset to run.")] = None,
    var: Annotated[
        list[str] | None, typer.Option("--var", help="Override a variable: key=value.")
    ] = None,
) -> None:
    """G2: explain reuse/rerun/refusal for every step, without running anything.

    Compares ``workflow`` as it stands today against what ``run`` actually recorded:
    each step's declared config, its resolved inputs, and whether its checkpointed
    value is still there and unchanged. Nothing here executes a step or writes
    anything -- a resume-plan is always safe to run before a real resume.
    """
    from sclpl.catalog import resolve as catalog
    from sclpl.project import context as project_context
    from sclpl.run import checkpoints, resume
    from sclpl.run.preflight import preflight
    from sclpl.run.sclpll.parse import _literal
    from sclpl.values import cache as cache_mod

    try:
        resolved_project = project_context.load()
        doc = catalog.resolve(
            workflow,
            extra_dirs=resolved_project.workflow_dirs if resolved_project is not None else None,
        ).doc
    except ValidationError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(error.exit_code) from error

    report = preflight(doc, mode=mode, check_files=False, require_ports=False)
    if not report.ok:
        for problem in report.problems:
            typer.echo(str(problem), err=True)
        raise typer.Exit(report.problems[0].exit_code)
    assert report.plan is not None and report.resolved is not None

    overrides = {}
    for item in var or []:
        name, separator, value = item.partition("=")
        if not separator or not name:
            typer.echo(f"--var expects name=value, got {item!r}", err=True)
            raise typer.Exit(EXIT_USAGE)
        overrides[name] = _literal(value)
    variables = {**doc.vars, **report.resolved.vars, **overrides}

    with (
        db.History() as history,
        checkpoints.Store() as store,
        cache_mod.Cache(cache_mod.default_root()) as cache,
    ):
        plan = asyncio.run(
            resume.plan_resume(
                doc, report, variables, run, history=history, store=store, cache=cache
            )
        )

    counts = plan.counts()
    typer.echo(
        f"{doc.name} resumed from {run}: {counts[resume.REUSE]} reuse, "
        f"{counts[resume.RERUN]} rerun, {counts[resume.REFUSE]} refuse"
    )
    for entry in plan.verdicts:
        mark = {"reuse": "=", "rerun": ">", "refuse": "!"}.get(entry.verdict, "?")
        typer.echo(f"  {mark} {entry.node_id:<28} {entry.verdict:<7} {entry.reason}")
    if plan.by_verdict(resume.REFUSE):
        raise typer.Exit(EXIT_USAGE)


@runs_app.command("recover-publication")
def runs_recover_publication(
    workflow: Annotated[str, typer.Argument(help="Workflow name, as it publishes under.")],
) -> None:
    """G4: complete or report on a publish this workflow's own last generation left
    behind after a crash -- a process killed partway through committing staged
    files to their real destinations.

    A no-op, safely, for a workflow whose last publish finished normally: there is
    nothing here to find. Locks every destination the interrupted generation would
    touch first, the same C5 guarantee a run itself holds, so this never races a
    concurrent run or another recovery attempt over the same files.
    """
    from sclpl.run import publication
    from sclpl.state import locking

    destinations = publication.pending_destinations(workflow)
    with locking.output_locks(destinations):
        report = publication.recover(workflow)

    if not report.found:
        typer.echo(f"{workflow}: nothing to recover", err=True)
        return
    if report.ambiguous:
        typer.echo(
            f"{workflow}: generation {report.generation} is stale -- "
            "a newer one has already published since. Nothing was touched.",
            err=True,
        )
        raise typer.Exit(EXIT_USAGE)
    if report.completed:
        typer.echo(f"  completed: {', '.join(report.completed)}")
    if report.already_committed:
        typer.echo(f"  already committed: {', '.join(report.already_committed)}")
    if report.tampered:
        typer.echo(
            f"  tampered (destination no longer matches; not trusted): "
            f"{', '.join(report.tampered)}",
            err=True,
        )
    if not report.ok:
        raise typer.Exit(EXIT_USAGE)


@runs_app.command("export")
def runs_export(
    run: RunArg,
    into: Annotated[Path | None, typer.Option("--into", help="Write here instead.")] = None,
) -> None:
    """One run, whole, as JSON. For sharing, or for a bug report."""
    with db.History() as history:
        payload = json.dumps(db.export(history, run), indent=2)
    if into is None:
        sys.stdout.write(payload + "\n")
    else:
        into.write_text(payload + "\n", encoding="utf-8")
        typer.echo(f"wrote {into}", err=True)


@runs_app.command()
def pin(
    run: RunArg,
    off: Annotated[bool, typer.Option("--off", help="Unpin it instead.")] = False,
) -> None:
    """Keep a run. Pinned runs survive pruning and do not count against the limit."""
    with db.History() as history:
        identifier = history.pin(run, pinned=not off)
    typer.echo(f"{'unpinned' if off else 'pinned'} {identifier}", err=True)


@runs_app.command()
def prune(
    keep: Annotated[int, typer.Option("--keep", help="How many to keep.")] = db.KEEP_DEFAULT,
) -> None:
    """Drop all but the most recent runs. Pinned ones are exempt."""
    with db.History() as history:
        dropped = history.prune(keep)
    typer.echo(f"dropped {len(dropped)} run{'' if len(dropped) == 1 else 's'}", err=True)


# -- secrets -------------------------------------------------------------------------


@secret_app.command("set")
def secret_set(
    name: Annotated[str, typer.Argument(help="What to call it.")],
    value: Annotated[str | None, typer.Argument(help="The secret. Omit to be prompted.")] = None,
    env: EnvOpt = "default",
) -> None:
    """Store a secret.

    Omit the value and it is prompted for without echo -- which also keeps it out of the
    shell history, where a secret passed as an argument would otherwise sit.
    """
    if value is None:
        value = typer.prompt(f"value for {name}", hide_input=True)
    backend = secrets.put(name, value, env=env)
    typer.echo(f"stored {name} in {backend.describe()}", err=True)


@secret_app.command("get")
def secret_get(name: Annotated[str, typer.Argument()], env: EnvOpt = "default") -> None:
    """Print a secret to stdout, so it can be piped."""
    found = secrets.get(name, env=env)
    if found is None:
        raise ValidationError(
            f"no secret named {name!r} in {env!r}",
            remedies=[f"sclpl secret set {name}", "sclpl secret list"],
        )
    sys.stdout.write(found + "\n")


@secret_app.command("list")
def secret_list(env: EnvOpt = "default") -> None:
    """The names that are stored. **Never the values.**"""
    found = secrets.names(env=env)
    if not found:
        typer.echo(f"nothing stored for {env!r}", err=True)
        if secrets.backend().name == "keyring":
            # Worth saying: the keyring has no portable enumeration, so an empty list
            # here does not mean an empty keyring.
            typer.echo("  (the OS keyring cannot be listed; `secret get` still works)", err=True)
        return
    for name in found:
        typer.echo(name)


@secret_app.command("remove")
def secret_remove(name: Annotated[str, typer.Argument()], env: EnvOpt = "default") -> None:
    """Forget a secret."""
    if secrets.delete(name, env=env):
        typer.echo(f"removed {name}", err=True)
    else:
        typer.echo(f"nothing named {name!r} in {env!r}", err=True)
        raise typer.Exit(EXIT_USAGE)


# -- doctor --------------------------------------------------------------------------


def doctor() -> None:
    """Check the installation, and say what is missing and how to get it.

    Every line is either fine or actionable. A diagnostic that reports a problem without
    the command that fixes it has moved the work rather than done it.
    """
    from sclpl import __version__
    from sclpl.ext import plugins as ext
    from sclpl.render import term
    from sclpl.values import cache, governor

    ok = True

    def line(label: str, good: bool, detail: str, fix: str = "") -> None:
        nonlocal ok
        ok = ok and good
        typer.echo(f"  {'ok ' if good else '!  '}{label:<16} {detail}")
        if not good and fix:
            typer.echo(f"     {'':<16} {fix}")

    typer.echo(f"sclpl {__version__}  ({sys.version.split()[0]} on {sys.platform})\n")

    line(
        "secrets",
        secrets.backend().name != "none",
        secrets.backend().describe(),
        "pip install 'sclpl[keyring]' or 'sclpl[crypto]'",
    )

    try:
        import pandas  # noqa: F401

        line("tables", True, "pandas is available")
    except ImportError:
        line(
            "tables",
            False,
            "pandas is not installed",
            "pip install 'sclpl[data]'  -- needed for Excel and Parquet",
        )

    try:
        import h2  # noqa: F401

        line("http/2", True, "h2 is available")
    except ImportError:
        line("http/2", True, "h2 is not installed; HTTP/1.1 will be used")

    caps = term.probe()
    line(
        "terminal",
        True,
        f"{caps.rung}, {caps.width}x{caps.height}, "
        f"{'colour' if caps.color else 'no colour'}, "
        f"{'unicode' if caps.unicode else 'ascii'}",
    )

    line(
        "memory",
        True,
        f"{governor.human(governor.rss())} in use, "
        f"budget {governor.human(governor.default_budget())}",
    )

    home = db.default_root()
    writable = _writable(home)
    line("home", writable, str(home), f"cannot write to {home}")

    cache_root = cache.default_root()
    line("cache", _writable(cache_root), str(cache_root))

    registry = ext.discover()
    refused = registry.refused()
    line(
        "plugins",
        not refused,
        f"{len(registry.loaded())} loaded" + (f", {len(refused)} refused" if refused else ""),
        "sclpl plugin list --refused",
    )

    typer.echo("")
    if not ok:
        typer.echo("some things need attention, listed above", err=True)
        raise typer.Exit(EXIT_USAGE)
    typer.echo("everything checks out")


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".sclpl-probe"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError:
        return False
    return True


# -- completion ------------------------------------------------------------------------

_SHELLS = ("bash", "zsh", "fish", "powershell")


def completion(
    shell: Annotated[str, typer.Argument(help=f"One of: {', '.join(_SHELLS)}.")],
) -> None:
    """Print a completion script, to be sourced.

    Printed rather than installed. Where a completion belongs differs by shell, by
    distribution, and by whether you use a framework, and guessing wrong leaves a file
    somewhere you did not ask for.
    """
    if shell not in _SHELLS:
        from sclpl.errors import did_you_mean

        remedies = []
        suggestion = did_you_mean(shell, list(_SHELLS))
        if suggestion:
            remedies.append(suggestion)
        remedies.append(f"one of: {', '.join(_SHELLS)}")
        raise ValidationError(f"no completion for {shell!r}", remedies=remedies)

    variable = "_SCLPL_COMPLETE"
    scripts: dict[str, str] = {
        "bash": f'eval "$({variable}=bash_source sclpl)"',
        "zsh": f'eval "$({variable}=zsh_source sclpl)"',
        "fish": f"{variable}=fish_source sclpl | source",
        "powershell": (
            f'$env:{variable} = "powershell_source"; sclpl | Out-String | Invoke-Expression'
        ),
    }
    where: dict[str, str] = {
        "bash": "~/.bashrc",
        "zsh": "~/.zshrc",
        "fish": "~/.config/fish/completions/sclpl.fish",
        "powershell": "$PROFILE",
    }
    typer.echo(scripts[shell])
    typer.echo(f"\n# add the line above to {where[shell]}", err=True)


def _echo_json(payload: Any) -> None:  # pragma: no cover - kept for symmetry
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
