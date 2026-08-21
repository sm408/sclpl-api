# Error Catalog

> Every error in SCLPLAPI, what causes it, and how to fix it.

---

## SCLPLL Compiler Errors

All compiler errors follow the format: `Line N: <message>`

| Error | Cause | Fix |
|-------|-------|-----|
| `Missing @workflow directive` | File has no `@workflow` line | Add `@workflow id "Name"` as the first directive |
| `Duplicate @workflow directive` | Two `@workflow` lines in one file | Keep only one `@workflow` per file |
| `Invalid @workflow syntax` | `@workflow` line doesn't match `@workflow <id> "Name"` | Use: `@workflow my-id "My Workflow Name"` |
| `Invalid @base_url syntax` | `@base_url` line is malformed | Use: `@base_url https://api.example.com` |
| `Invalid @var syntax` | `@var` line missing `=` | Use: `@var name = value` |
| `Invalid @step syntax` | `@step` line doesn't match expected format | Use: `@step id -> output` or `@step id <- dep -> output` |
| `Unknown directive: @X` | `@`-prefixed keyword isn't recognized | Valid directives: `@workflow`, `@base_url`, `@var`, `@step` |
| `Unexpected line` | Non-indented line outside a step body | Indent step body lines or add a directive |
| `Unknown step body syntax: X` | Indented line doesn't match known keywords | Use: `request`, `func`, `header`, `body`, `@when`, `@foreach`, `@repeat`, `@semaphore` |

---

## Function Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Function 'X' not found` | No `.py` file with matching `@name` | Check `@name` in docstring matches `func X` in `.sclpll`; file must be in `functions/` |
| `Function 'X' has no run(ctx) entrypoint` | File exists but lacks `run` function | Add `def run(ctx): return ctx` to the file |
| `Function X failed: <exception>` | Exception during function execution | Check function code; add logging with `logger = logging.getLogger(__name__)` |
| `ImportError` in function | Missing Python package | `pip install <package>` |

### Function Discovery Checklist

1. File is in `functions/` or a subdirectory
2. File has a docstring with `@name`, `@type`, `@version`
3. `@name` value matches exactly (case-sensitive) what's in `func X`
4. File has a `def run(ctx)` function
5. File is valid Python (no syntax errors)

```bash
# List all discovered functions
python -m app functions
```

---

## Workflow Execution Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Unsupported step type: X` | Step type isn't `request`, `function`, or `delay` | Check the `type` field in your step definition |
| `Request not found: X` | Step references a request_id that doesn't exist | Use inline `request METHOD URL` syntax or save the request first |
| `Request timed out` | HTTP request exceeded 30s timeout | Check API reachability; add retry logic |
| `Retry failed` | All retry attempts exhausted | Check the API endpoint; increase retry count |
| `Dependency not satisfied (upstream failure)` | A dependency step failed, blocking downstream | Fix the failing upstream step |
| `Variable not found: X` | `{{X}}` references an undefined variable | Define with `@var X = value` or set in environment |

---

## Parallel Workflow Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Dependency not satisfied (upstream failure)` | Deadlock: remaining steps depend on failed steps | Check which step failed; fix it or remove the dependency |
| `Unsupported step type: X` | Same as workflow errors | Same fix |
| `Request not found: X` | Same as workflow errors | Same fix |
| `[N] <error>` (foreach/repeat) | Individual iteration failed in a loop | Check the error per-iteration; data may be malformed |

---

## HTTP Request Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Request timed out` | Server didn't respond in 30s | Check URL, server status, network |
| `ConnectError` / `ConnectionRefused` | Can't reach the server | Check URL, firewall, VPN |
| `NameResolutionError` | DNS lookup failed | Check domain name spelling |
| `HTTP 4xx/5xx` | Server returned an error | Check auth, URL, request body |

---

## CLI Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Environment 'X' not found` | `--env X` doesn't match any environment | `python -m app env list` to see available |
| `CSV file not found: X` | Batch file path doesn't exist | Check the path; use absolute path |
| `History entry 'X' not found` | ID doesn't match any history entry | `python -m app history list` to see IDs |
| `Collection 'X' not found` | Collection ID prefix not found | `python -m app collection list` to see IDs |
| `Request 'X' not found` | Request ID prefix not found | `python -m app collection requests <col-id>` to see requests |
| `Unknown format: X` | Export format isn't `json` or `csv` | Use `--format json` or `--format csv` |
| `Workflow file not found: X` | Workflow JSON path doesn't exist | Check the path |
| `Format: KEY=VALUE` | Variable argument missing `=` | Use: `python -m app env set-var env KEY=VALUE` |

---

## TUI Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `File not found: X` | Script path doesn't exist | Check the path |
| `Cannot read file: X` | OS error reading file | Check permissions |
| `Parse error: X` | SCLPLL syntax error | See Compiler Errors above |
| `Invalid JSON: X` | JSON syntax error | Validate at jsonlint.com |
| `Unsupported file type: X` | File isn't `.sclpll` or `.json` | Use a supported file type |
| `Validation Failed` | Script has syntax errors | See the common fixes in the panel |
| `No functions discovered` | `functions/` is empty or missing | Create a function file with proper metadata |
| `No .sclpll files found` | No scripts in current dir or `examples/` | Provide a path manually |

---

## Plugin Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Plugin directory not found: X` | Plugin `plugins/X` doesn't exist | Create the directory or install the plugin |
| `Plugin dependency 'X' not found` | Required plugin isn't installed | Install the dependency plugin |
| `Plugin dependency 'X' failed to load` | Dependency loaded but not active | Check the dependency's error status |
| `Failed to discover plugin in X` | `plugin.json` is malformed | Fix the manifest file |
| `Failed to load hook X from plugin Y` | Hook module has errors | Check the hook's Python code |

---

## Database Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Database not connected` | Access before initialization | Internal error; report as bug |
| SQLite corruption | Database file is corrupted | Delete `data/sclplapi.db` and restart |

---

## Variable Resolution Errors

Variable resolution doesn't raise errors — it silently returns the literal `{{key}}` string.

| Symptom | Cause | Fix |
|---------|-------|-----|
| Output contains `{{var_name}}` | Variable not defined | Define with `@var` or in environment |
| Output contains `{{step.field}}` | JSON path doesn't exist in step output | Check the step's actual response structure |
| Output contains `{{step.list[5]}}` | List index out of range | Check list length in step output |

---

## Event Bus Errors

Event handler errors are logged but don't stop execution.

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Event handler error for X` in logs | Exception in an event handler | Check the handler code |
| `Wildcard event handler error` in logs | Exception in a `*` handler | Check the wildcard handler code |

---

## Getting More Detail

```bash
# Validate a script without running
python -m app.core.engine.sclpll_cli validate script.sclpll

# Run with verbose output
python -m app.core.engine.sclpll_cli run script.sclpll --verbose

# Check compiled output
python -m app.core.engine.sclpll_cli compile script.sclpll
cat workflow.json

# List discovered functions
python -m app functions

# List environments and variables
python -m app env list
python -m app env vars <env-name>

# Check history for errors
python -m app history list
python -m app history inspect <id>
```
