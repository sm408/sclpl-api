"""The bare-invocation launcher: a numbered menu.

Rules it follows (SPEC section 15), each for a reason:

- **It prints the command before running it, and asks.** The menu is a way to discover
  the CLI, not a replacement for it. Someone who uses it five times should be able to
  type the command themselves the sixth.
- **Plain line prompts only.** No cursor addressing, so it sits below the render ladder
  and cannot fight the live region for the terminal.
- **Numbers, plus `q` and `?` at every level.** One convention, everywhere.
- **`Ctrl-C` backs out one level; twice exits.**
- **Nothing destructive without naming the target.**

It holds no state and duplicates no logic: every choice ends in the same argument
vector a person could have typed.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass

import typer

from sclpl.catalog import resolve as resolver
from sclpl.cli.options import EXIT_OK, EXIT_USAGE


@dataclass(frozen=True, slots=True)
class Choice:
    label: str
    build: Callable[[], list[str] | None]
    hint: str = ""


def is_interactive() -> bool:
    """The menu appears only on a real terminal, at both ends.

    stdin must be a tty because it prompts; stderr must be one because that is where
    the prompts go. Either being redirected means this is a script, and a script that
    hits a menu hangs.
    """
    try:
        return sys.stdin.isatty() and sys.stderr.isatty()
    except (AttributeError, ValueError):
        return False


def launch() -> int:
    """Show the menu. Returns the exit code for the process."""
    typer.echo("sclpl — pick something to do, or 'q' to quit", err=True)
    while True:
        try:
            argv = _menu()
        except KeyboardInterrupt:
            typer.echo("", err=True)
            return EXIT_OK
        if argv is None:
            return EXIT_OK
        if not argv:
            continue
        code = _confirm_and_run(argv)
        if code is not None:
            return code


def _menu() -> list[str] | None:
    choices = [
        Choice("Run a saved workflow", _run_saved, "pick from the catalogue"),
        Choice("Run a workflow file", _run_path, "give a path"),
        Choice("Validate a workflow", _validate, "check without running"),
        Choice("Explain a workflow", _explain, "show the plan"),
        Choice("List workflows", lambda: ["list"]),
        Choice("Send one request", _call, "sclpl call"),
        Choice("Import a workflow", _import, "register a file"),
        Choice("Help", lambda: ["--help"]),
    ]

    typer.echo("", err=True)
    for index, choice in enumerate(choices, start=1):
        hint = f"  ({choice.hint})" if choice.hint else ""
        typer.echo(f"  {index}. {choice.label}{hint}", err=True)
    typer.echo("  q. Quit", err=True)

    answer = _ask("choose")
    if answer is None or answer.lower() in ("q", "quit", "exit"):
        return None
    if answer == "?":
        typer.echo("  Type a number, or q to quit.", err=True)
        return []
    if not answer.isdigit() or not 1 <= int(answer) <= len(choices):
        typer.echo(f"  '{answer}' is not one of 1-{len(choices)}.", err=True)
        return []
    return choices[int(answer) - 1].build()


def _confirm_and_run(argv: list[str]) -> int | None:
    """Show the exact command, confirm, then run it as a subprocess.

    A subprocess rather than an in-process call so the run gets a clean terminal: the
    live region installs and restores exactly as it would have if the command had been
    typed, and nothing the run does can leave the menu in a strange state.
    """
    printable = "sclpl " + " ".join(_quote(part) for part in argv)
    typer.echo(f"\n  $ {printable}", err=True)
    answer = _ask("run it? [Y/n]")
    if answer is None:
        return None
    if answer.strip().lower() in ("n", "no"):
        return None

    result = subprocess.run([sys.executable, "-m", "sclpl", *argv], check=False)
    typer.echo("", err=True)
    return result.returncode if result.returncode else None


def _quote(part: str) -> str:
    return f'"{part}"' if " " in part else part


def _ask(prompt: str) -> str | None:
    """One line of input. `Ctrl-C` and EOF both back out."""
    try:
        return input(f"  {prompt}> ").strip()
    except (KeyboardInterrupt, EOFError):
        typer.echo("", err=True)
        return None


def _pick_workflow() -> str | None:
    known = sorted(resolver.available())
    if not known:
        typer.echo("  no workflows found — import one first.", err=True)
        return None
    typer.echo("", err=True)
    for index, name in enumerate(known, start=1):
        typer.echo(f"  {index}. {name}", err=True)
    answer = _ask("workflow")
    if answer is None or answer.lower() == "q":
        return None
    if answer.isdigit() and 1 <= int(answer) <= len(known):
        return known[int(answer) - 1]
    if answer in known:
        return answer
    typer.echo(f"  no workflow named {answer!r}.", err=True)
    return None


def _with_mode_and_files(name: str, command: str) -> list[str] | None:
    argv = [command, name] if command else [name]
    try:
        located = resolver.resolve(name)
    except Exception:  # noqa: BLE001 - the run itself will report it properly
        return argv

    doc = located.doc
    if doc.modes:
        typer.echo(f"  modes: {', '.join(doc.modes)} (Enter for default)", err=True)
        mode = _ask("mode")
        if mode is None:
            return None
        if mode:
            argv.extend(["--mode", mode])

    for port in (*doc.inputs, *doc.outputs):
        label = f"{port.direction if hasattr(port, 'direction') else ''}{port.name}"
        default = f" [{port.default}]" if port.default else ""
        optional = "" if port.required else " (optional, Enter to skip)"
        answer = _ask(f"{label}{default}{optional}")
        if answer is None:
            return None
        if answer:
            argv.append(answer)
        elif port.default:
            argv.append(port.default)
        elif port.required:
            typer.echo(f"  {port.name} is required.", err=True)
            return None
    return argv


def _run_saved() -> list[str] | None:
    name = _pick_workflow()
    if name is None:
        return None
    return _with_mode_and_files(name, "run")


def _run_path() -> list[str] | None:
    path = _ask("path to a .sclpll or .json file")
    if not path:
        return None
    return _with_mode_and_files(path, "run")


def _validate() -> list[str] | None:
    name = _pick_workflow()
    return ["validate", name] if name else None


def _explain() -> list[str] | None:
    name = _pick_workflow()
    return ["explain", name] if name else None


def _call() -> list[str] | None:
    method = _ask("method [GET]") or "GET"
    url = _ask("url")
    if not url:
        return None
    return ["call", method.upper(), url]


def _import() -> list[str] | None:
    path = _ask("path to a workflow file")
    return ["import", path] if path else None


def bare_shorthand(argv: list[str]) -> list[str] | None:
    """`sclpl orders partial in.csv out.csv` -> `run orders --mode partial …`.

    Decision 2: the shorthand exists for the command line, and scripts use `sclpl run`
    explicitly. It only fires when the first argument actually resolves to a workflow,
    so a mistyped subcommand still gets "no such command" rather than being taken for a
    workflow name.
    """
    if not argv:
        return None
    first = argv[0]
    if first.startswith("-"):
        return None
    try:
        located = resolver.resolve(first)
    except Exception:  # noqa: BLE001 - not a workflow; let Typer report it
        return None

    rest = list(argv[1:])
    out = ["run", first]
    if rest and rest[0] in located.doc.modes:
        out.extend(["--mode", rest.pop(0)])
    out.extend(rest)
    return out


def maybe_launch() -> int:
    """What a bare `sclpl` does: the menu on a terminal, help and exit 2 otherwise."""
    if is_interactive():
        return launch()
    return EXIT_USAGE
