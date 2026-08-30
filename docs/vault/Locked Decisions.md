# Locked Decisions

Changing one of these needs an ADR in `docs/adr/` recording date, reason, and migration
impact. See [[Decision Log]] for the ones that have been changed.

## 1 The command is `sclpl`

No `sclplapi` alias. One name, so documentation and muscle memory agree.

## 2 Bare shorthand is supported

`sclpl <wf> [mode] [in…] [out…]` works, but scripts and CI use `sclpl run`. The
shorthand is for typing; the explicit form is for reading.

→ [[Modes and Ports#Positional binding]]

## 3 pandas and Excel ship as the `[data]` extra

Missing extras are reported **by preflight, never mid-run**. A pipeline that dies at the
write step, after every request has been paid for, is the failure this prevents.

→ [[Tables and Flattening]]

## 4 SCLPLL v2 is a clean break

No v1 converter. A v1 file fails at its first directive with a message saying so, which
is better than importing it wrong.

→ [[SCLPLL Reference]]

## 5 Run history in SQLite, retention default 5

Pinned runs are exempt. #todo *(M9)*

## 6 TUI, FastAPI, and SPA are deleted, not deprecated

Not marked legacy, not left importable — removed. Deprecation would have meant keeping
them working.

→ [[M0 Deletion]]

## 7 The terminal layer is hand-written; `rich` is not a dependency

Two reasons, both load-bearing. A live region must survive a worker pool writing
underneath it, which needs control over the write path. And a terminal bug in a user's
shell is not reproducible, so the code that draws has to be code we can read.

→ [[The Terminal Layer]]

## 8 SQLite ships as a bundled *plugin*, not core

Which is how we know the plugin API is sufficient: if the bundled plugin needs something
the API does not offer, the API is wrong. #todo *(M8)*

## Dependencies

Five, each doing three or four jobs: `httpx`, `typer`, `pydantic`, `aiosqlite`,
`pyarrow`. **Adding a sixth needs a reason in the commit message.**

Extras: `[data]` (pandas, openpyxl), `[keyring]`, `[dev]`.
