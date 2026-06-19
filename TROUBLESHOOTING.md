# TROUBLESHOOTING.md

> Solutions to common problems. If your issue isn't here, check the [Error Catalog](docs/ERROR_CATALOG.md).

---

## Installation Issues

### `pip install -e .` fails

**Symptom:** Build errors or missing dependencies.

**Fix:**
```bash
# Ensure you have Python 3.10+
python --version

# Upgrade pip
python -m pip install --upgrade pip

# Install in a clean virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -e .
```

### `ModuleNotFoundError: No module named 'app'`

**Symptom:** Running `python -m app` fails.

**Fix:** Make sure you ran `pip install -e .` from the project root. The `-e` flag installs in development mode. Verify:
```bash
pip show sclplapi
```

---

## Unicode Errors on Windows

### `UnicodeEncodeError: 'charmap' codec can't encode character`

**Symptom:** TUI or output crashes with encoding errors on Windows.

**Fix:**
```powershell
# Option 1: Set environment variable before running
$env:PYTHONIOENCODING="utf-8"
python -m app tui

# Option 2: Use the -X flag
python -X utf8 -m app tui

# Option 3: Use Windows Terminal (supports Unicode natively)
```

**Permanent fix:** Add to your PowerShell profile:
```powershell
$env:PYTHONIOENCODING="utf-8"
```

### `UnicodeDecodeError` reading files

**Symptom:** Error when reading `.sclpll` or `.json` files with special characters.

**Fix:** Ensure your files are saved as UTF-8. In VS Code, click the encoding in the status bar and select "UTF-8".

---

## SCLPLL Compilation Errors

### `Parse error: Line N: Missing @workflow directive`

**Cause:** Every `.sclpll` file must start with a `@workflow` directive.

**Fix:**
```sclpll
@workflow my-id "My Workflow Name"
    Description of what this workflow does.

@step first_step -> output
    request GET https://api.example.com/data
```

### `Parse error: Line N: Invalid @step syntax`

**Cause:** The `@step` line doesn't match the expected format.

**Fix:**
```sclpll
# Correct formats:
@step fetch_data -> output_var              # No dependencies
@step process <- fetch_data -> result       # One dependency
@step merge <- step_a, step_b -> combined   # Multiple dependencies

# Wrong:
@step fetch_data ->                         # Missing output var
@step process fetch_data -> result          # Missing <-
```

### `Parse error: Line N: Unknown step body syntax`

**Cause:** An indented line under `@step` doesn't match any known syntax.

**Fix:** Step body must start with one of: `request`, `func`, `header`, `body`, `@when`, `@foreach`, `@repeat`, `@semaphore`.

```sclpll
@step fetch_data -> output
    request GET https://api.example.com/data    # Correct: starts with 'request'
    header Accept: application/json              # Correct: starts with 'header'
```

### `Parse error: Line N: Unknown directive: @something`

**Cause:** A `@`-prefixed keyword isn't recognized.

**Fix:** Valid directives: `@workflow`, `@base_url`, `@var`, `@step`. Everything else is invalid.

---

## Function Errors

### `Function 'X' not found`

**Cause:** The function name in `func X` doesn't match any discovered function.

**Fix:**
1. Check the function file exists in `functions/` (or subdirectories)
2. Check the `@name` in the docstring matches exactly (case-sensitive):
   ```python
   """
   @name: Extract User Names    # Must match 'func Extract User Names' in .sclpll
   @type: transformer
   @version: 1
   """
   ```
3. List discovered functions:
   ```bash
   python -m app functions
   ```

### `Function 'X' has no run(ctx) entrypoint`

**Cause:** The Python file exists but doesn't have a `run` function.

**Fix:**
```python
"""
@name: My Function
@type: transformer
@version: 1
"""

def run(ctx):       # Must be named exactly 'run'
    # ... your logic ...
    return ctx      # Must return ctx
```

### `ImportError` in function

**Cause:** A function imports a package that isn't installed.

**Fix:**
```bash
pip install <package-name>
```

Or add it to `requirements.txt` and reinstall:
```bash
pip install -e .
```

---

## Workflow Execution Errors

### `Dependency not satisfied (upstream failure)`

**Cause:** A step depends on another step that failed, causing a deadlock.

**Fix:**
1. Check which step failed in the output
2. Fix the failing step (usually a bad URL or missing function)
3. Steps without dependencies will still run; only dependent steps are blocked

### `Request not found: X`

**Cause:** A workflow step references a `request_id` that doesn't exist.

**Fix:** For inline requests, use `request METHOD URL` syntax directly:
```sclpll
@step fetch_data -> output
    request GET https://api.example.com/data
```

### `Request timed out`

**Cause:** An HTTP request took longer than 30 seconds.

**Fix:**
- Check if the API is reachable
- Add retry logic in your workflow
- The timeout is currently hardcoded at 30s

### Workflow runs but output is `{{variable_name}}`

**Cause:** A variable wasn't resolved. The literal `{{...}}` string is returned.

**Fix:**
1. Check the variable is defined with `@var` or set in your environment
2. Check spelling matches exactly (case-sensitive)
3. Check the variable is set before it's used (step ordering)

---

## Database Issues

### `Database not connected. Call connect() first.`

**Cause:** Code tried to access the database before initialization.

**Fix:** This is an internal error. If you see it, report it as a bug. It shouldn't happen during normal CLI or TUI usage.

### Database is corrupted

**Symptom:** SQLite errors on startup.

**Fix:**
```bash
# Delete the database (loses history and environments)
rm data/sclplapi.db

# Restart - it will be recreated
python -m app tui
```

---

## Performance Issues

### Workflows are slow

**Possible causes:**
1. **Sequential when parallel is possible:** Remove unnecessary `<-` dependencies
2. **API latency:** Check individual step durations in the output
3. **Large responses:** Functions processing large JSON can be slow

**Diagnosis:**
```bash
# Run with timing visible
python -m app.core.engine.sclpll_cli run script.sclpll

# Use the performance analyzer tool
python tools/performance_analyzer.py output/execution_stats.json
```

### TUI is slow or flickers

**Cause:** Terminal rendering issues, especially over SSH.

**Fix:**
- Use the CLI instead: `python -m app.core.engine.sclpll_cli run script.sclpll`
- Increase terminal refresh: not currently configurable

---

## Environment Issues

### `Environment 'X' not found`

**Cause:** The environment name doesn't exist.

**Fix:**
```bash
# List existing environments
python -m app env list

# Create it
python -m app env create X
```

### Variables not applying

**Cause:** Wrong environment is active, or variable isn't set.

**Fix:**
```bash
# Check which env is active
python -m app env list

# Check variables in the active env
python -m app env vars <env-name>

# Set the variable
python -m app env set-var <env-name> key=value
```

---

## Still Stuck?

1. Check the [Error Catalog](docs/ERROR_CATALOG.md) for every possible error
2. Run with verbose output: `python -m app.core.engine.sclpll_cli run script.sclpll --verbose`
3. Validate your script: `python -m app.core.engine.sclpll_cli validate script.sclpll`
4. Check the [User Guide](docs/perspectives/user/README.md) for detailed examples
5. Open an issue: https://github.com/sm408/sclpl-api/issues
