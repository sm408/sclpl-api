# Concepts

The words this tool uses, and what they mean.

Read this page from top to bottom the first time: each concept only depends on the ones
above it. Come back later as a glossary.

For *why* any of these are the way they are, the Obsidian vault at `docs/vault/` has a
note per concept. This page is the short version.

---

## Map

| Layer | Concepts |
|---|---|
| Authoring | [Workflow](#workflow), [Step](#step), [Reference](#reference), [Port](#port), [Mode](#mode) |
| Execution | [Plan](#plan), [Lane](#lane), [Pagination](#pagination), [Cache](#cache), [Governor](#governor) |
| Data | [Value](#value), [Expression](#expression), [Table](#table), [Flattening](#flattening) |
| Operations | [Plugin](#plugin), [Run](#run), [Secret](#secret) |

## Workflow

A file describing what to fetch, how to shape it, and where to put it. Two surfaces —
**SCLPLL** (whitespace-significant, the one you write) and **JSON** (the one a program
writes) — over one internal representation, so they cannot drift into two dialects.

`sclpl convert` moves between them. `sclpl fmt` writes canonical form.

## Step

One thing a workflow does. Eight kinds: `http`, `fn`, `let`, `foreach`, `if`, `while`,
`gate`, `parallel` (and `use`, which is not implemented and says so).

A step's **id** is also the name its value binds to. `@fetch` means "what the step
called `fetch` produced".

The built-in `python` function is a function step that runs a registered, SHA-256-pinned Python
script. Its registration can name a project-local file or a provider URI such as `azblob://...`.
It passes an optional workflow value as JSON on stdin and turns JSON stdout into the next step
value.

## Reference

`@name`, and the only way a dependency is created. Reading `@orders` makes your step
wait for `orders` — there is no dependency list to keep in sync, and one cannot fall out
of date with the code.

This is why a step running in the wrong order is nearly always a reference you forgot
was in a string.

## Value

What a step produced, kept as the **Python object it actually is**. A number stays a
number, a list of records stays a list of records. Nothing is stringified between steps.

The single exception is `{{expr}}` inside a string, which is a boundary you asked for.
A bare `@ref` outside a string passes the object through.

## Expression

`count(@orders.body.data)`, `@a.total > 500`, `@items[?(price > 10)].id`.

Infix is sugar: `a > b` is `gt(a, b)`. There is one dispatch table, and an operator is
chosen by the runtime type of its first argument. It is never `eval()`.

## Port

A named file the workflow expects, rather than a path baked into it.

```
@input customers:csv
@output report:csv
```

Bound at the command line — by name (`--out report=x.csv`), by position, or from a
declared default. `-` means stdin or stdout. A step says `-> report` to write to one;
the workflow says *what*, the caller says *where*.

## Mode

A named subset. `sclpl run orders -m partial` runs the steps `partial` includes.

A mode can only **subtract** steps and override scalars. It can never add a step, change
what depends on what, or alter an expression — and pruning something a kept step needs
fails at validate time rather than at runtime.

## Plan

The graph, after the mode has pruned it. Built from references, checked for cycles, and
scored so the longest remaining chain starts first.

`sclpl explain` prints it.

## Lane

Where a step runs: the event loop (waiting on a socket), a thread (blocking calls), or a
process (CPU-bound work over a large payload). Chosen from what the function is and how
big its arguments are, and overridable with `lane process`.

## Table

Records with columns. Backed by pandas when the `[data]` extra is installed, behind a
wrapper — which is what makes pandas optional rather than required.

## Flattening

Nested JSON into columns. `{"customer": {"name": "Ada"}}` becomes `customer_name`.
Arrays of scalars join with commas; arrays of objects are JSON-encoded, unless you
`explode` them into one row each.

Column order is stable across runs, because a spreadsheet formula refers to column D.

## Pagination

Following a source to its end. Five strategies — `cursor`, `token`, `page`, `offset`,
`link_header`. The merged result keeps the shape a single page had, so `@fetch.body.data`
means the same thing on page 40 as on page 1.

## Cache

Not doing the same work twice. Keyed by everything that could change the answer and
nothing else — the mode is deliberately excluded, so a partial run and a full run share
the fetch they have in common.

Five flags: default, `--refresh`, `--no-cache`, `--offline`, `--http-cache`.

## Governor

Watches memory. At 70% of the budget it writes intermediates to disk; at 85% it halves
how much it admits at once. A run holding three times its budget finishes slowly rather
than dying.

Spilling is not freeing — the value is still readable, just on disk.

## Plugin

A package contributing connectors, functions, operators, or a table backend. Declares
what it needs (`network`, `fs:write`, …) in a manifest; `--deny-capability` refuses to
load one that asked for something you did not want.

There is no sandbox. A plugin is trusted code, and the guarantee is about *loading*
rather than about running — which is the guarantee that can actually be kept.

Ordinary scripts run with `sclpl python` or a workflow `python` step are trusted code too. Their
registered alias and SHA-256 pin prevent an arbitrary path or silently changed Blob from running;
they do not sandbox the code.

## Run

One execution. Recorded in a local SQLite history with its steps, timings, and ports,
plus a self-contained NDJSON log so it is greppable without the database.

`sclpl runs list | show | search | diff | replay | export | pin | prune`.

## Secret

A credential, in the OS keyring — or an encrypted file, on a machine with no keyring.
If neither is available, `sclpl` **refuses to store it** rather than falling back to
something weaker.

Redaction happens in the reporter, so a component that forgets to redact cannot leak.
