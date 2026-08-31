---
tags:
  - concept
---

# Plugins

`ext/plugins.py` finds them, `ext/api.py` is what they may use.

## Discovery

Three places, in order (SPEC §11):

1. `importlib.metadata.entry_points(group="sclpl.plugins")` — anything `pip install`ed
2. `./plugins/` — the one you are writing, in the project you are writing it for
3. `~/.sclpl/plugins/` — the ones you keep

Plus the bundled set, which goes through **exactly the same path**. That is the point of
shipping them.

Order matters only for shadowing, and shadowing is **reported** rather than resolved
silently. Two plugins claiming one name is a thing to know about, not a coin toss.

## The manifest

```toml
[plugin]
name = "postgres"
version = "1.2.0"
api = "sclpl/1"
module = "postgres"
capabilities = ["network", "secrets:read"]

[[connector]]
name = "postgres.query"
lane = "thread"
summary = "Run a query."
```

The ABI is a single integer. A plugin built against an API that no longer exists fails
**at load, with both versions named**, rather than at the first call with an
`AttributeError` from inside somebody else's package.

## Nothing broken is fatal

A malformed manifest, a module that will not import, a `register()` that raises — each
produces a **refused** plugin, listed by `sclpl plugin list` with the reason. One broken
plugin should not stop a run that does not use it.

> A refusal recorded while reading the manifest is not overwritten by a later check.
> Continuing would replace the actual problem (unreadable TOML) with a symptom of it
> ("names no module") and send the reader to the wrong line.

## Capabilities

`network`, `fs:read`, `fs:write`, `secrets:read`, `subprocess`. An unknown one is
refused rather than ignored: a typo in a manifest must not silently widen or narrow what
is granted.

```bash
sclpl --deny-capability network run wf.sclpll
```

**There is no sandbox.** A plugin is trusted code — a Python package the user chose to
install — and anything that could sandbox it could be bypassed by it. What exists is a
*declaration*, and `--deny-capability` refuses to **load** anything that asked for one
you did not want.

That is an honest guarantee about loading, which is a smaller claim than a guarantee
about running, and it is the one that can actually be kept.

> [!note] Why the flag is read from `sys.argv`
> Loading a plugin *runs* its module. A capability refused after the option parser has
> run has already been exercised. `cli/app.py:_denied_capabilities` therefore reads the
> flag before `bootstrap.load()`; the parser still validates it, so a typo is an error
> and not a denial of nothing.

## The public API

`sclpl.ext.api` — and nothing else. Not a technical restriction, because Python has none
to offer; a promise in one direction:

> Anything in that module keeps working across a minor version. Anything outside it may
> be rearranged without warning.

| Contribution | Register with |
|---|---|
| a function | `@function` |
| a connector | `@connector` — the dot is what namespaces it |
| an operator overload | `@overload` |
| a table backend | `set_backend` |
| a rehydrator | `register_reader` |

`register()` in the plugin's module is called once at load, for anything that needs the
engine to exist first. The decorators have already run by then — importing is what
registers them.

## The bundled set

| | |
|---|---|
| `sqlite` | `query`, `write`, `exec`, `schema`. No new dependency; `sqlite3` is stdlib |
| `fs` | `glob`, `stat`, `exists`, `copy`, `move`, `remove`, `mkdir` |
| `example` | The scaffold template — loaded on every run, so it cannot rot |

SQLite ships as a plugin rather than as core
([[Locked Decisions#8 SQLite ships as a bundled *plugin*, not core]]) precisely so the
API is exercised by something real.

**It worked.** Writing `sqlite.write` found that `records_of` — a public API function —
did not understand a `Table`. It produced `[{"value": "<Table 3x3>"}]`: the repr, in one
column. The function catalogue had worked around it privately, so only a plugin ever hit
it. → [[Decision Log]]

## `sclpl plugin`

| | |
|---|---|
| `list` | What is installed, where from, what it may do, and what was refused |
| `describe <name>` | Everything it declares, and everything it actually registered |
| `scaffold <name>` | A working plugin you can edit |
| `install <src>` | Prints the `pip` command. It does not run it |

`describe` shows *declared* and *registered* separately, and the difference is worth
seeing: a manifest naming a connector the code forgot is a bug in the plugin.

`install` deliberately does not run pip. Doing so would guess at the environment, the
index, and whether you meant `--user`, and be wrong in a way that is hard to unpick.

→ [[Extending sclpl]], [[ext]], [[plugins_bundled]]
