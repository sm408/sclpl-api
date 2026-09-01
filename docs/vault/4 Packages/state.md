---
tags:
  - package
---

# `state/`

Budget 900. What persists between runs.

| File | Job |
|---|---|
| `secrets.py` | Keyring, then encrypted file, then refuse → [[Secrets]] |
| `db.py` | Run history and NDJSON logs → [[Run History]] |

## Both refuse rather than degrade

`secrets.py` will not store a credential somewhere weak, and says which of two extras to
install. That is [[Why a Rewrite|defect 4]] made impossible.

`db.py` wraps its own writes: a run that produced its files has succeeded whether or not
it could also write a row about itself.

Two failures, two opposite handlings — and the difference is whether the thing being
protected is the *user's* interest or the tool's convenience.

## `sqlite3`, not `aiosqlite`

History writes once per run. An async driver would buy nothing, and `aiosqlite` was
dropped in M9 after being declared and never used.
