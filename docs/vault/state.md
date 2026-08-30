# `state/`

Budget 900. Persistent state. **Empty — M9.** #todo

Planned:

| File | Job |
|---|---|
| `db.py` | SQLite run history; `run_ports`, retention, pinning |
| `settings.py` | Config load / merge / show |
| `secrets.py` | Keyring-first, **no base64 fallback** |

The base64 fallback is [[Why a Rewrite|defect 4]] and must not come back —
[[Invariants#9 Secrets never reach a log, a label, or a trace]].

`docs/attic/carried/storage/` holds the v1 code kept for this milestone.
