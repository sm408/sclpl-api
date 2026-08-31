---
tags:
  - package
---

# `cli/`

Budget 1,400. The Typer surface: commands, global flags, the bare launcher.

| File | Job |
|---|---|
| `app.py` | The Typer root, global flags, subcommand registration |
| `options.py` | Exit codes, verbosity resolution, shared option types |
| `run.py` | `call` — one request |
| `workflow_cmd.py` | `run`, `validate`, `explain`, `fmt`, `convert` |
| `catalog_cmd.py` | `import`, `list`, `show`, `remove` |
| `plugin_cmd.py` | `plugin list`, `describe`, `scaffold`, `install` |
| `launcher.py` | The bare `sclpl <wf> …` shorthand |

## Registration

Commands are registered by the module that owns them, so a milestone adds its surface in
one place. **Nothing is stubbed**: if `--help` lists a command, that command works. A
command that is not implemented is not registered.

## Bootstrap

`app.py` calls `bootstrap.load()` at import, before any command can be routed — so
`--help`, completion, and preflight all see the same function set a run would.

## Global flags come first

`sclpl -vv run wf`, not `sclpl run wf -vv`. Typer's convention, and the reason `run
--help` does not list `-v`.

→ [[Running and Debugging]], [[Errors and Exit Codes]]
