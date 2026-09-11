# Software Engineer: Extend the Runtime

This path is for someone who works on the execution model, creates reusable function libraries,
or builds plugins that contribute connectors and capabilities.

## Understand the extension boundary

External code should import from `sclpl.ext.api` or `sclpl.ext.functions`. The bundled plugins
are examples of the same public surface used by third-party packages.

Resource providers use the same boundary: import `ResourceProvider`, `ResourceRef`,
`ResourceInfo`, `ResourceCapabilities`, and `register_resource_provider` from
`sclpl.ext.api`, never from runner internals. Core owns staging and publication sequencing;
the provider owns URI parsing, authentication, transfer, revision tokens, and SDK errors.

```bash
python -m sclpl plugin list
python -m sclpl plugin describe text
python -m sclpl plugin scaffold my_plugin
```

Plugins declare capabilities such as network or filesystem access. Users can deny a capability
before loading plugins:

```bash
python -m sclpl --deny-capability network plugin list
```

Plugins are trusted Python code, not sandboxed code. The capability contract controls loading
policy and makes the requested access visible.

## Build a resource provider

Implement `normalize`, `resolve`, `stat`, `exists`, `download`, `upload`, and `display_uri`.
Redact credentials in `display_uri` and map stale conditional writes to `ResourceConflict`.
Test with the core `memory://` lifecycle before adding a provider integration test such as
Azurite. Do not add provider-specific scheme parsing or SDK objects to the runner.

## Run the plugin example

```bash
python -m sclpl validate examples/persona-software-engineer-plugin.sclpll
python -m sclpl run examples/persona-software-engineer-plugin.sclpll labels.json
```

The workflow uses the bundled text plugin to extract labels, slug them, number the records,
and write JSON. It exercises plugin discovery through the real CLI.

## Build a function library

Functions should have a narrow signature, a useful docstring, and explicit failure behaviour.
The registry generates reference documentation from those declarations:

```bash
python -m sclpl docs build
python -m sclpl docs build --check
```

Never hand-edit `docs/reference/`. Add tests for successful values, invalid values, and any
security-sensitive path.

## Choose a script or a plugin

Use the built-in `python` workflow function for a registered project script. Register a local
`path` or provider `uri` under `[python.scripts.NAME]` and pin its SHA-256; workflows and the
standalone form (`sclpl python NAME [ARGS...]`) accept only that alias. It forwards `args` as
command-line arguments and connects `input`/stdout with JSON. Registered scripts remain trusted
code in the active environment; this is an execution allowlist, not a sandbox.

Choose a plugin instead when callers need installation/discovery, a stable named connector, or
capability declarations that users can deny before the plugin imports.

## Work on the engine safely

The important invariants are:

- stdout is data and stderr is interface.
- Values remain typed between steps.
- The DAG is inferred from references.
- Expressions never use `eval()` or `exec()`.
- Secrets never reach logs, labels, traces, fixtures, or snapshots.

Run the full gates before submitting a change:

```bash
python -m ruff check sclpl tests scripts
python -m ruff format --check sclpl tests scripts
python -m mypy
python -m pytest -q
python scripts/check_budget.py
python scripts/check_layering.py
python scripts/check_vault.py
python -m sclpl docs build --check
```
