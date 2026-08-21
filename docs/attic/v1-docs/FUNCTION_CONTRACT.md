# Function Contract

## Overview

The function system is SCLPLAPI's Python-native extensibility layer. Functions are plain `.py` files with a docstring-based metadata header and a `run(ctx)` entrypoint. The engine discovers them from the filesystem, loads them dynamically, and passes a shared `ExecutionContext`.

Functions are the primary way users add custom logic to workflows — transforming data, authenticating requests, exporting results, and chaining steps together.

## Function Types

| Type | When it runs | Typical use |
|------|-------------|-------------|
| `pre_request` | Before an HTTP request is sent | Add auth headers, sign payloads, set dynamic URLs |
| `post_response` | After an HTTP response is received | Log responses, extract tokens, validate status codes |
| `transformer` | As a standalone workflow step | Process data, aggregate results, generate reports |
| `auth_token` | When authentication is needed | Fetch and cache OAuth tokens, generate JWTs |
| `exporter` | At the end of a pipeline | Write files (CSV, JSON, Excel), push to external services |

## Metadata Format

Every function file must start with a docstring containing `@key: value` pairs:

```python
"""
@name: My Function
@type: transformer
@version: 1

Optional description of what this function does.
"""
```

### Required fields

| Field | Description |
|-------|-------------|
| `@name` | Human-readable function name. Used for discovery and display. |
| `@type` | One of: `pre_request`, `post_response`, `transformer`, `auth_token`, `exporter` |

### Optional fields

| Field | Description |
|-------|-------------|
| `@version` | Integer version string (default: `1`) |
| `@description` | Longer description (or use free text below the `@` lines in the docstring) |

The engine's `_parse_metadata()` method reads these via AST parsing — the module is not imported during discovery.

## The `run(ctx)` Entrypoint

Every function must define a module-level `run` function:

```python
def run(ctx):
    # ... do work ...
    return ctx
```

- The function receives a single argument: `ctx` (an `ExecutionContext` instance).
- It **must return `ctx`** — the engine passes it to the next step.
- Both sync and async `run()` functions are supported. The engine checks `asyncio.iscoroutine()` and awaits if needed.

```python
async def run(ctx):
    result = await some_async_call()
    ctx.workflow_variables["result"] = result
    return ctx
```

## ExecutionContext Schema

The `ExecutionContext` is a `dataclass` defined in `app/core/models/context.py`:

```python
@dataclass
class ExecutionContext:
    request: RequestDef | None = None
    environment: Environment | None = None
    variables: dict[str, str] = field(default_factory=dict)
    step_outputs: dict[str, Any] = field(default_factory=dict)
    batch_row: dict[str, str] = field(default_factory=dict)
    workflow_variables: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
```

### Field descriptions

| Field | Type | Description |
|-------|------|-------------|
| `request` | `RequestDef \| None` | The current HTTP request definition (method, url, headers, body). `None` for function-only steps. |
| `environment` | `Environment \| None` | The active environment with its variables. `None` if no environment is active. |
| `variables` | `dict[str, str]` | Resolved template variables for the current step. |
| `step_outputs` | `dict[str, Any]` | Outputs from completed steps, keyed by step ID. Each value is typically a dict with `status_code`, `body`, `headers`, etc. |
| `batch_row` | `dict[str, str]` | The current row data when running inside a batch/foreach loop. Empty dict otherwise. |
| `workflow_variables` | `dict[str, str]` | Shared variables across the entire workflow. Functions read from and write to this dict. |
| `metadata` | `dict[str, Any]` | Engine-populated metadata (response object, timing, etc.). |

## Accessing Step Outputs

Previous step results are available in `ctx.step_outputs`:

```python
def run(ctx):
    # Get output from a specific step by ID
    fetch_result = ctx.step_outputs.get("fetch_data", {})
    status_code = fetch_result.get("status_code")
    body = fetch_result.get("body")

    # Handle nested JSON
    import json
    if isinstance(body, str):
        data = json.loads(body)
    else:
        data = body
    return ctx
```

Step outputs are populated by the engine after each step completes. For request steps, the output is typically:

```python
{
    "status_code": 200,
    "body": '{"key": "value"}',
    "headers": {"content-type": "application/json"},
    "duration_ms": 142
}
```

## Storing Results

Functions store results in `ctx.workflow_variables` for downstream steps:

```python
def run(ctx):
    # Store a simple value
    ctx.workflow_variables["user_count"] = "42"

    # Store structured data as JSON string
    import json
    ctx.workflow_variables["summary"] = json.dumps({"total": 42, "ok": True})

    return ctx
```

Downstream steps and functions can then read these values:

```python
def run(ctx):
    count = ctx.workflow_variables.get("user_count", "0")
    return ctx
```

## Return Value

**Functions must return `ctx`.** The engine passes the (possibly mutated) context to the next step in the pipeline. Returning `None` or a different object will break the workflow.

```python
def run(ctx):
    ctx.workflow_variables["done"] = "true"
    return ctx  # Always return ctx
```

## Error Handling

Functions signal errors by raising exceptions. The engine catches all exceptions and records them as step failures:

```python
def run(ctx):
    data = ctx.step_outputs.get("fetch", {})
    if not data:
        raise ValueError("No data from fetch step — cannot process")

    if data.get("status_code", 0) >= 400:
        raise RuntimeError(f"Upstream error: {data['status_code']}")

    return ctx
```

The engine wraps this in a `FunctionResult`:

```python
@dataclass
class FunctionResult:
    name: str
    success: bool
    return_value: Any = None
    error: str | None = None
    duration_ms: int = 0
```

Do **not** catch exceptions inside your function to silently continue — let them propagate so the engine can record the failure and (optionally) trigger retry or skip logic.

## Examples

### pre_request — Add Authorization Header

```python
"""
@name: Add Bearer Token
@type: pre_request
@version: 1
"""

def run(ctx):
    token = ctx.workflow_variables.get("api_token", "")
    if ctx.request and token:
        ctx.request.headers.append(
            RequestParam(key="Authorization", value=f"Bearer {token}")
        )
    return ctx
```

### post_response — Log and Extract Token

```python
"""
@name: Extract Auth Token
@type: post_response
@version: 1
"""

import json
import logging

logger = logging.getLogger(__name__)

def run(ctx):
    response = ctx.metadata.get("response")
    if response:
        body = getattr(response, "body", "{}")
        if isinstance(body, str):
            data = json.loads(body)
        else:
            data = body
        token = data.get("access_token")
        if token:
            ctx.workflow_variables["api_token"] = token
            logger.info("Extracted auth token")
    return ctx
```

### transformer — Process Data

```python
"""
@name: Process Single User
@type: transformer
@version: 1
"""

import json

def run(ctx):
    user_raw = ctx.workflow_variables.get("current_user", "{}")
    user = json.loads(user_raw) if isinstance(user_raw, str) else user_raw

    summary = {
        "user_id": user.get("id"),
        "name": user.get("name"),
        "email": user.get("email"),
    }

    existing = ctx.workflow_variables.get("processed_users", "[]")
    processed = json.loads(existing)
    processed.append(summary)
    ctx.workflow_variables["processed_users"] = json.dumps(processed)
    return ctx
```

### auth_token — Fetch OAuth Token

```python
"""
@name: Fetch OAuth Token
@type: auth_token
@version: 1
"""

import httpx

def run(ctx):
    client_id = ctx.workflow_variables.get("client_id", "")
    client_secret = ctx.workflow_variables.get("client_secret", "")

    resp = httpx.post("https://auth.example.com/token", data={
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    })
    resp.raise_for_status()

    data = resp.json()
    ctx.workflow_variables["access_token"] = data["access_token"]
    return ctx
```

### exporter — Write CSV

```python
"""
@name: Export Weather Data
@type: exporter
@version: 1
"""

import csv
import json
from pathlib import Path

def run(ctx):
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    record = {
        "date": ctx.workflow_variables.get("today", "unknown"),
        "city": ctx.workflow_variables.get("city", "unknown"),
        "temp": ctx.workflow_variables.get("temp_c", "N/A"),
    }

    csv_path = output_dir / "weather.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=record.keys())
        writer.writeheader()
        writer.writerow(record)

    ctx.metadata["export_result"] = {"csv": str(csv_path)}
    return ctx
```

## File Naming Conventions

- Function files are plain `.py` files.
- Use `snake_case` for filenames: `process_single_user.py`, `export_weather.py`.
- Files starting with `_` are skipped by discovery (e.g., `__init__.py`, `_helpers.py`).
- Subdirectories are supported: `functions/transformers/extract_date.py`.
- The filename does not need to match the `@name` metadata — the engine uses `@name` for lookup, falling back to the file stem if no metadata is found.

## Discovery Mechanism

Functions are discovered via `FilesystemFunctionRunner.discover()`:

1. Start at the configured `base_dir` (default: `functions/`).
2. Recursively glob for `*.py` files using `pathlib.Path.rglob("*.py")`.
3. Skip files whose name starts with `_`.
4. Parse each file's AST to extract the module-level docstring.
5. Extract `@key: value` pairs from the docstring.
6. If `@name` is present, include the function in the discovery results.

The runner caches nothing — each `discover()` call re-scans the filesystem. This means adding or modifying function files takes effect immediately without restarting the application.

### Lookup by name

When the engine needs to run a specific function (by `@name` or file stem):

1. Scan all `*.py` files under `base_dir` with `rglob`.
2. Parse metadata from each file.
3. Return the first file where `meta["name"] == name` or `path.stem == name`.
4. If not found, return `None` and the engine reports a "Function not found" error.

## Security Model

Functions run with full local process privileges. There is no sandboxing — this is intentional for a local-first tool. Functions can:

- Read and write any file on the filesystem
- Make network requests
- Import any installed Python package
- Execute subprocesses

Treat function files as trusted code. Do not run untrusted function files.
