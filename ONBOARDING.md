# ONBOARDING.md

> From zero to productive in 20 minutes.

---

## Minute 0: Install

```bash
# Clone and install
git clone https://github.com/sm408/sclpl-api.git
cd sclpl-api
pip install -e .

# Verify it works
python -m app tui
```

You should see the SCLPLAPI splash screen. Press **Q** to quit.

### Choose Your Interface

| Interface | Command | Status |
|-----------|---------|--------|
| Terminal UI | `python -m app tui` | Implemented |
| Web GUI | `python -m app web` | Planned |

Both share the same database and functions directory.

---

## Minute 1: Your First Workflow

Create `hello.sclpll`:

```sclpll
@workflow hello-api "Hello API"
    My first SCLPLAPI workflow.

@base_url https://jsonplaceholder.typicode.com

@step fetch_users -> users_data
    request GET {{base_url}}/users

@step show_names <- fetch_users -> names
    func Extract User Names
```

Run it:

```bash
python -m app.core.engine.sclpll_cli run hello.sclpll
```

**What happened:**
1. `fetch_users` made a GET request to the JSONPlaceholder API
2. The response was stored in `users_data`
3. `show_names` waited for `fetch_users`, then ran the `Extract User Names` function

---

## Minute 5: Custom Functions

Create `functions/extract_names.py`:

```python
"""
@name: Extract User Names
@type: transformer
@version: 1
"""

import json


def run(ctx):
    raw = ctx.step_outputs.get("fetch_users", {})
    body = raw.get("body", "[]")
    users = json.loads(body) if isinstance(body, str) else body
    names = [u.get("name", "") for u in users]
    ctx.workflow_variables["user_names"] = json.dumps(names)
    return ctx
```

**The function contract:**
- Docstring must have `@name`, `@type`, `@version`
- Must have a `run(ctx)` function
- Access step outputs via `ctx.step_outputs`
- Store results in `ctx.workflow_variables`
- Always return `ctx`

**Function types:**

| Type | When it runs | Use case |
|------|-------------|----------|
| `transformer` | As a pipeline step | Map, filter, merge data |
| `exporter` | At pipeline end | Write output files |
| `pre_request` | Before HTTP call | Add auth headers |
| `post_response` | After HTTP call | Transform responses |

---

## Minute 10: Parallel Workflows

Steps without dependencies run automatically in parallel:

```sclpll
@workflow parallel-demo "Parallel Fetch"
    Fetches three APIs at the same time.

@base_url https://jsonplaceholder.typicode.com

# These three run in parallel (no <- dependency)
@step fetch_users -> users
    request GET {{base_url}}/users

@step fetch_posts -> posts
    request GET {{base_url}}/posts

@step fetch_todos -> todos
    request GET {{base_url}}/todos

# This waits for all three to finish
@step merge <- fetch_users, fetch_posts, fetch_todos -> combined
    func Merge All Data
```

**Key rule:** If a step has no `<-` dependency, it runs immediately. Steps with dependencies wait for all upstream steps.

---

## Minute 15: Variables and Environments

### Variables

```sclpll
@var api_key = sk-abc123
@var timeout = 30
@var city = London

@step get_weather -> weather
    request GET https://wttr.in/{{city}}?format=j1
```

### Environments

```bash
# Create environments
python -m app env create development
python -m app env create production

# Set variables
python -m app env set-var development api_key=sk-test123
python -m app env set-var production api_key=sk-prod456

# Activate one
python -m app env activate development

# Run with a specific environment
python -m app.core.engine.sclpll_cli run hello.sclpll --env production
```

---

## Minute 20: Full Export and Backup

### Export History

```bash
# Export to JSON
python -m app export --format json --output backup.json

# Export to CSV
python -m app export --format csv --output history.csv --limit 500
```

### Export from a Workflow

Add an export function at the end of your pipeline:

```python
"""
@name: Export Report
@type: exporter
@version: 1
"""

import json
from pathlib import Path


def run(ctx):
    output = Path("output")
    output.mkdir(exist_ok=True)

    data = {
        "users": ctx.workflow_variables.get("user_names"),
        "timestamp": ctx.metadata.get("execution_time"),
    }

    with open(output / "report.json", "w") as f:
        json.dump(data, f, indent=2)

    return ctx
```

---

## What's Next?

| Want to... | Read... |
|-----------|---------|
| Learn all SCLPLL syntax | [docs/SCLPLL_LANGUAGE.md](docs/SCLPLL_LANGUAGE.md) |
| See every error and its fix | [docs/ERROR_CATALOG.md](docs/ERROR_CATALOG.md) |
| Get a one-page reference | [docs/CHEATSHEET.md](docs/CHEATSHEET.md) |
| Fix a problem | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |
| Understand the architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Contribute to the project | [CODING_STANDARDS.md](CODING_STANDARDS.md) |
| See working examples | `examples/` directory |

---

## Quick Reference

```bash
# TUI (interactive)
python -m app tui

# Web GUI (planned)
python -m app web

# Run a workflow
python -m app.core.engine.sclpll_cli run script.sclpll

# Validate a script
python -m app.core.engine.sclpll_cli validate script.sclpll

# Compile (generates workflow.json + run.py)
python -m app.core.engine.sclpll_cli compile script.sclpll

# List functions
python -m app functions

# List history
python -m app history list

# Run tests
pytest tests/ -v
```
