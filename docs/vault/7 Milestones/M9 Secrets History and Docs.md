---
tags:
  - milestone
---

# M9 Secrets, History, and Docs

**Done. The last milestone.**

## Exit criterion

> A new user imports a shared workflow and finishes a paginated API → CSV run from the
> README in ten minutes.

Met, and tested as written: `test_a_new_user_gets_from_the_readme_to_a_csv` types every
command the README gives, in the order it gives them, and ends with 30 rows across three
pages in a CSV.

A second test asserts every command the README *promises* actually exists — because
"nothing is stubbed" is only true if something checks.

## What landed

| | |
|---|---|
| `state/secrets.py` | Keyring, then encrypted file, then **refuse** → [[Secrets]] |
| `state/db.py` | Run history and NDJSON logs → [[Run History]] |
| `cli/admin_cmd.py` | `runs`, `secret`, `doctor`, `completion` |
| `cli/docs_cmd.py` | `docs build`, with a `--check` drift gate |
| `functions/secrets_fns.py` | `secret()` and `has_secret()` in a workflow |
| `docs/playbooks/` | Four, each with a runnable example |
| `docs/concepts.md` | Every word, in dependency order |
| `README.md` | Rewritten as the ten-minute path |

## What building it found

**A pruned writer's port was still required.** `--mode smoke` prunes the step that writes
`report`, and preflight still demanded a file for it. Demanding a file for something
nothing will write is asking for a promise nobody will keep. An output port is now
optional when the mode pruned every step that claims it with `-> port` — and only when
some step claims it at all, because a workflow writing literal paths has told us nothing
about who writes what.

**`aiosqlite` was declared and unused.** Four packages, one of them dead. Both SQLite
users write once per run or sub-millisecond per step, so stdlib `sqlite3` is enough.
An unused dependency is worse than an extra one: it installs, it is audited, it appears
in every lockfile, and it does nothing.

**The drift gate caught its own author.** `sclpl docs build --check` failed the first
time it ran in CI, because `secret()` had been added after the reference was generated.
Which is the gate working.

## The four dependencies

`httpx`, `typer`, `pydantic`, `pyarrow`. Each does three or four jobs.

## What is deliberately not here

- **`use`** — invoking another workflow as a step. It raises a named error pointing at
  where to look, rather than doing nothing quietly. #todo
- **Arrow IPC handoff** to the process lane, which pickles instead. Works, slower. #todo
- **Lane assignment from run history**, which now has the history to learn from but no
  code that reads it. #todo
- **HTTP revalidation round trips.** `--http-cache` sets the policy and stores ETags;
  sending them is not wired. #todo

All four are written down here rather than left to be discovered, which is the point of
writing them down.
