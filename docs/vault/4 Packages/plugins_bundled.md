---
tags:
  - package
---

# `plugins_bundled/`

Budget 600. The three plugins that ship with `sclpl`.

| | Contributes | Capabilities |
|---|---|---|
| `sqlite/` | `sqlite.query`, `.write`, `.exec`, `.schema` | `fs:read`, `fs:write` |
| `fs/` | `fs.glob`, `.stat`, `.exists`, `.copy`, `.move`, `.remove`, `.mkdir` | `fs:read`, `fs:write` |
| `example/` | `greet`, `example.echo` | none |

All three go through the same discovery, manifest, and capability path as an external
plugin, and import **only** from `sclpl.ext.api`. → [[Plugins]]

## Why SQLite is here and not in core

[[Locked Decisions#8 SQLite ships as a bundled *plugin*, not core]]: if a bundled plugin
needs something the public API does not offer, the API is wrong, and we find out before
anyone else does.

It worked on the first try. `records_of` -- a public API function -- did not understand a
`Table`, and only a plugin could have hit it. → [[Decision Log]]

## Why `example` is loaded, not just stored

It is what `sclpl plugin scaffold` writes. Loading it on every run means it cannot
quietly stop working, and a scaffold that no longer runs is worse than none -- it costs
an hour before you suspect it.

## `sqlite3` adds no dependency

It is in the standard library. Everything runs in the thread lane, declared in the
manifest: `sqlite3` blocks, and blocking on the event loop stalls every other step,
including ones whose HTTP responses have already arrived. → [[Lanes]]
