---
tags:
  - concept
---

# Run History

`state/db.py`. What happened, kept so it can be asked about later.

## Two records, not one

Every run writes **a row** in SQLite *and* **a self-contained NDJSON log** beside it.

The log is not redundant. History you can only reach through a query language is history
most people will not reach at all, and `grep` is the tool everyone already has:

```bash
grep '"status":"failed"' ~/.sclpl/logs/*.ndjson
```

It is written **during** the run, as a second sink on the reporter — not assembled
afterwards from memory. A log put together at the end is a log that is missing whatever
crashed.

## What is stored

| Table | |
|---|---|
| `runs` | id, name, workflow, mode, timings, status, exit code, step counts, cache stats, peak RSS, argv |
| `run_steps` | per step: status, lane, duration, attempts, error, whether it was cached |
| `run_ports` | which file each port was bound to |
| `run_tags` | `--tag nightly` |

## Finding one again

```bash
sclpl runs list
sclpl runs show abc            # id, name, or a unique prefix of either
sclpl runs search "connection refused"
```

A **prefix** is enough, because the id is a hash and nobody wants to type eight
characters correctly. An ambiguous prefix lists the candidates rather than picking one.

`search` covers names, workflows, modes, tags, **and step errors** — which is what you
have when something broke and you do not know what it was called.

> `LIKE` rather than FTS5. The corpus is a few hundred short rows and the query is one
> word; requiring an FTS5 build would make history unavailable on exactly the machines
> least likely to have one.

## Retention

**Five**, by default ([[Locked Decisions#5 Run history in SQLite, retention default 5]]).
Applied after each run.

Pinned runs are exempt **and not counted**:

```bash
sclpl runs pin abc12345
sclpl runs prune --keep 2      # two pinned + two recent = four kept
```

A pin means "keep this", not "spend the budget on this". Pinning three with `keep 5`
still leaves five unpinned — otherwise pinning would silently evict everything else.

## Comparing and repeating

```bash
sclpl runs diff yesterday today
sclpl runs replay abc          # prints the command
sclpl runs export abc --into bug.json
```

`diff` puts **status first and timing last**. A run that failed where the other succeeded
is the answer to "what changed"; a hundred milliseconds is not.

`replay` prints rather than executes. A replay is usually wanted *with* a change — a
different mode, a fresh cache, one more page — and a command you can edit is more use
than one that has already gone.

## Never the run's verdict

Recording is wrapped in a `try`. A run that produced its files has succeeded whether or
not it could also write a row about itself, and a read-only home directory should not
turn a good run into a failed one.

## `sqlite3`, not `aiosqlite`

A run writes here once, at the end, when there is nothing left to block. An async driver
would buy nothing and cost a dependency — which is why `aiosqlite` was dropped in M9
after being declared and never used. → [[Decision Log]]

→ [[Secrets]], [[Errors and Exit Codes]]
