---
tags:
  - milestone
---

# M8 Plugins

**Done.**

## Exit criterion

> SQLite → join with an API → write back, no config; an external plugin `pip install`s
> and works.

Both halves met.

**The round trip.** Seven steps, no configuration: seed a SQLite table, read it back,
fetch a paginated API, left-join the two on `id`, write the result to a second table,
read *that* back, and save it.

```json
[{"id": 1, "note": "local one",   "name": "row-1"},
 {"id": 3, "note": "local three", "name": "row-3"},
 {"id": 5, "note": "local five",  "name": "row-5"}]
```

**An external plugin.** `sclpl plugin scaffold mything` writes a plugin that loads and
runs immediately -- both its function and its connector are callable with no edits. A
scaffold needing three fixes before it works teaches the wrong thing about how hard this
is.

## What landed

| | |
|---|---|
| `ext/plugins.py` | Discovery, manifest, ABI check, capabilities, refusals |
| `ext/api.py` | The public API, and the promise attached to it |
| `plugins_bundled/sqlite` | query, write, exec, schema |
| `plugins_bundled/fs` | glob, stat, exists, copy, move, remove, mkdir |
| `plugins_bundled/example` | The scaffold template, loaded every run so it cannot rot |
| `cli/plugin_cmd.py` | list, describe, scaffold, install |
| `--deny-capability` | Refuses to *load* anything declaring one |

→ [[Plugins]]

## What building it found

**`records_of` did not understand a `Table`.** This is the one that justifies the whole
approach. It is a *public API* function, and given a `Table` it returned
`[{"value": "<Table 3x3>"}]` -- the repr, in a single column. The function catalogue had
its own private wrapper that handled tables first, so nothing inside `sclpl` ever hit it.
Only a plugin could.

Locked decision 8 says SQLite ships as a plugin "which is how we know the plugin API is
sufficient". It was not, and writing `sqlite.write` is what showed that.

**The expression grammar had no dotted calls.** `sqlite.write(@rows, db, 'people')`
parsed as attribute access on a variable named `sqlite`, then failed on the paren. A
connector is namespaced by a dot, so the grammar had to accept a dotted callee -- rooted
at a bare identifier, never at a `@ref`, because `@response.body(...)` would be calling a
value.

**A refusal was overwritten by a symptom.** A plugin refused while its manifest was being
read went on through the ABI and capability checks, and came out reported as "names no
module" -- true, but a consequence of the TOML being unreadable, and it points at the
wrong line.

**A diagnostic raised in the root callback showed a traceback.** Individual commands
caught `SclplError`; nothing caught one raised while parsing a global option. Handled at
the entrypoint now, so no code path can turn a message we wrote to be read into a stack
trace with the message buried in it.

## Not in this milestone

`use` -- invoking another workflow as a step -- still raises its named error. It shares a
resolution path with the catalogue, but it is a *workflow* feature rather than a plugin
one, so it remains outside the completed plugin milestone. #todo
