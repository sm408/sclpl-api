# A1 — compatibility baseline

Snapshot date: 2026-09-06, taken from `integration/unified-upgrade` before Batch A
completed. This is the public surface every later batch must keep working; a change
here is a compatibility decision, not an incidental refactor. Enforced by
`tests/integration/test_compat_baseline.py`.

## Top-level commands

`python -m sclpl --help` lists exactly these top-level commands, in this order:

```text
call, run, validate, explain, graph, fmt, convert, import, list, show, remove,
init, doctor, completion, contract, plugin, project, env, test, workflow, runs,
secret, docs
```

Removing one, or renaming it without a documented deprecation, is a breaking change.
Adding a new command is not.

## Global options

`-q`/`--quiet`, `-v`/`--verbose`, `--json`, `--plain`, `--no-color`,
`--deny-capability`, `--version`, `--help`. Verbosity clamps to `[-2, 3]`
(`sclpl/cli/options.py`).

## Exit codes (`sclpl/errors.py`)

| Code | Name | Meaning |
|---|---|---|
| 0 | `EXIT_OK` | success |
| 1 | `EXIT_STEP_FAILED` | a step ran and did not succeed |
| 2 | `EXIT_USAGE` | bad CLI usage |
| 3 | `EXIT_VALIDATION` | the workflow is not runnable as written |
| 4 | `EXIT_ASSERTION` | an `assert` rule was false |
| 5 | `EXIT_CACHE_MISS` | `--offline` and the value is not cached |
| 6 | `EXIT_UNKNOWN_TARGET` | no such workflow/mode/function/plugin |
| 130 | `EXIT_INTERRUPTED` | Ctrl-C, or a cancelled run |

These numbers are part of the CLI contract; scripts depend on them (SPEC section 15).
New failure categories get a diagnostic identifier within an existing code, not a new
numeric code, unless a compatibility ADR says otherwise (plan section 4).

## `runs export` JSON shape (`sclpl.state.db.export`)

```json
{
  "run": { "...RunRecord columns, snake_case..." },
  "tags": ["..."],
  "ports": [{ "direction": "...", "name": "...", "path": "...", "digest": "..." }],
  "steps": [{ "step_id": "...", "status": "...", "duration_ms": 0, "error": null }]
}
```

## Plugin manifest / ABI (`sclpl.ext.plugins.Plugin`)

- `api` is `"sclpl/{API_VERSION}"`; a plugin declaring a different major number is
  refused before its module imports (A3).
- Required-shape fields: `name`, `version`, `api`, `capabilities`, `source`, `module`,
  `contributes` (list of `{kind, name, lane, summary}`).
- Capabilities are drawn from a closed set (`sclpl.ext.plugins.CAPABILITIES`); an
  unknown capability is a refusal, not a silent pass-through.

## `call --json` event sequence

For a single successful request: `run_started`, `step_started`, `step_finished`,
`run_finished`, in that order, each a JSON object with an `"event"` key and a `"ts"`
key (`tests/integration/test_call.py::test_json_mode_emits_ndjson_on_stderr` already
pins this; recorded here so a future change to that test is recognized as a
compatibility decision rather than a fixture update).

## What this baseline does not cover

Performance budgets are tracked separately (plan section 8, task J3) once there is a
stable benchmark machine to calibrate against; this snapshot fixes the *shape* of the
public surface, not its throughput.
