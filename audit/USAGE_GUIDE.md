# SCLPLAPI Usage Guide

> From zero to running workflows in 5 minutes.

---

## Installation

```bash
# Clone the repo
git clone https://github.com/sm408/sclpl-api.git
cd sclpl-api

# Install dependencies
pip install -e .

# For Web GUI support (planned)
pip install -e ".[web]"
```

---

## Quick Start

### 1. Launch the TUI

```bash
python -m app tui
```

You'll see the ASCII art logo and main menu:

```
  ____  ____  ____  ____  ____  _      ____  ____  ____
 / ___)( __ \( ___)( ___)(  _ \( \    / ___)( ___)(  _ \
( (__  /    / )__)  )__)  )   / ) \   \___ \ )__)  )   /
 \___)\_\_\_)(____)(____)(_)\_)(___)  (____/(___)(_)\_)

  API Workflow Studio  ·  Python-First  ·  Local-First

┌──────────────────────── Main Menu ─────────────────────────┐
│  R       │  Run Workflow          │  Execute a .sclpll     │
│  L       │  Load Script           │  Load and parse        │
│  F       │  Browse Functions      │  View discovered       │
│  H       │  View History          │  Browse past runs      │
│  E       │  Manage Environments   │  Create/activate       │
│  V       │  Validate Script       │  Check syntax          │
│  Q       │  Quit                  │  Exit                  │
└────────────────────────────────────────────────────────────┘
```

Press **R** to run a workflow, **F** to browse functions, **Q** to quit.

### 2. Launch the Web GUI (Planned)

```bash
python -m app web
```

Opens a browser at `http://localhost:8000` with:

```
┌──────────────┬─────────────────────────────────────────────┐
│              │                                             │
│  Home        │  Welcome dashboard with stats cards         │
│  Request     │  Method selector, URL, params, headers,     │
│  Editor      │  body editor with Send button               │
│  Collections │  Organize requests into folders              │
│  Workflows   │  Run and monitor .sclpll workflows          │
│  Flow        │  Visual canvas for workflow graphs           │
│  Builder     │                                             │
│  Functions   │  Browse and search Python functions          │
│  History     │  Color-coded request log                     │
│  Settings    │  Base URL, theme, timeout                    │
│              │                                             │
└──────────────┴─────────────────────────────────────────────┘
```

### Switching Between TUI and GUI

Both interfaces share the same SQLite database and `functions/` directory. Launch whichever you prefer:

```bash
# Terminal UI
python -m app tui

# Web GUI (planned)
python -m app web
```

Your collections, history, and environments are available in both.

---

### 2. Write Your First Workflow

Create a file called `my_first.sclpll`:

```sclpll
# My First SCLPLAPI Workflow
# Fetches data from two endpoints in parallel, then analyzes it.

@workflow my-first-workflow "My First Workflow"
    A simple parallel workflow example.

@base_url https://jsonplaceholder.typicode.com

# These two steps run in parallel (no dependencies)
@step fetch_users -> users_data
    request GET {{base_url}}/users

@step fetch_posts -> posts_data
    request GET {{base_url}}/posts

# This step waits for both to complete
@step analyze <- fetch_users, fetch_posts -> analysis
    func Analyze Data
```

---

### 3. Run It

```bash
# Run directly from .sclpll
python -m app.core.engine.sclpll_cli run my_first.sclpll

# Or compile first, then run
python -m app.core.engine.sclpll_cli compile my_first.sclpll
python examples/my_first/run.py
```

**Output:**

```
============================================================
  My First Workflow
============================================================

  [OK] fetch_users  (448ms)
  [OK] fetch_posts  (400ms)
  [OK] analyze  (5ms)

============================================================
  PASSED in 653ms
============================================================
```

---

## SCLPLL Language Reference

### Directives

| Directive | Purpose | Example |
|-----------|---------|---------|
| `@workflow` | Define workflow | `@workflow id "Name"` |
| `@base_url` | Set base URL | `@base_url https://api.example.com` |
| `@var` | Define variable | `@var api_key = sk-123` |
| `@step` | Define step | `@step fetch_data -> data` |

### Step Types

**Request (HTTP call):**
```sclpll
@step fetch_users -> users_data
    request GET {{base_url}}/users
    header Accept: application/json
    header Authorization: Bearer {{api_key}}
```

**Function (Python):**
```sclpll
@step process <- fetch_users -> processed
    func Process User Data
```

### Dependencies

```sclpll
# No dependency = runs immediately (parallel)
@step fetch_a -> data_a
    request GET {{base_url}}/a

# With dependency = waits for fetch_a
@step process_a <- data_a -> result
    func Process A

# Multiple dependencies = waits for all
@step merge <- fetch_a, fetch_b -> merged
    func Merge Data
```

### Variables

```sclpll
@base_url https://api.example.com
@var api_key = sk-abc123
@var timeout = 30

@step auth_request -> response
    request GET {{base_url}}/protected
    header Authorization: Bearer {{api_key}}
```

### Dot Notation (Nested JSON)

When a step returns nested JSON like `{"user": {"name": "John", "address": {"city": "NYC"}}}`:

```sclpll
@step greet <- fetch_user
    request GET {{base_url}}/greet?name={{fetch_user.user.name}}&city={{fetch_user.user.address.city}}
```

### Loops

**@foreach — iterate over a collection:**
```sclpll
@step process_each <- fetch_users -> processed
    @foreach {{fetch_users.body}} as user
    func Process Single User
```

**@repeat — execute N times:**
```sclpll
@step batch_fetch -> results
    @repeat 5
    request GET {{base_url}}/items/{{_index}}
```

### Conditional Execution

```sclpll
@step success_path <- check_status
    @when {{check_status.status_code}} == 200
    request GET {{base_url}}/data

@step fallback_path <- check_status
    @when {{check_status.status_code}} != 200
    request GET {{base_url}}/fallback
```

### Rate Limiting

```sclpll
@step slow_api -> data
    @semaphore 2
    request GET {{base_url}}/slow-endpoint
```

---

## CLI Commands

```bash
# Launch TUI
python -m app tui

# Launch Web GUI (planned)
python -m app web

# Run a workflow
python -m app.core.engine.sclpll_cli run script.sclpll

# Compile .sclpll to workflow.json + run.py
python -m app.core.engine.sclpll_cli compile script.sclpll

# Decompile workflow.json back to .sclpll
python -m app.core.engine.sclpll_cli decompile workflow.json

# Validate a script
python -m app.core.engine.sclpll_cli validate script.sclpll

# Run tests
pytest tests/ -v

# Run tools
python tools/workflow_validator.py workflow.json
python tools/function_linter.py functions/
python tools/performance_analyzer.py output/execution_stats.json
```

---

## Web GUI Features (Planned)

### Home Dashboard
- Welcome message with quick-start links
- Stats cards: total requests, collections, workflows, functions
- Click any card to navigate to that section

### Request Editor
- **Method selector**: GET, POST, PUT, DELETE, PATCH
- **URL input**: with environment variable resolution
- **Tabs**: Params, Headers, Body
- **Send button**: executes request and shows response
- **Response panel**: status code, time, size, formatted JSON body

### Collections
- Create, rename, delete collections
- Add requests to collections
- Click collection to expand and see requests

### Workflows
- List all `.sclpll` workflows
- Run button with live progress
- Step timing and status indicators

### Flow Builder
- Visual canvas for workflow graphs
- Color-coded nodes (HTTP = blue, Function = green)
- Click node to see details
- Drag to reposition

### Functions
- Browse all discovered Python functions
- Click to view source code
- Search/filter by name or type

### History
- Table of past requests
- Color-coded methods (GET = green, POST = blue, PUT = orange, DELETE = red)
- Color-coded statuses (2xx = green, 4xx = yellow, 5xx = red)
- Filter by method

### Settings
- Base URL configuration
- Theme selector (light/dark)
- Request timeout

---

## Troubleshooting

**"Function not found"**
- Check `@name` in function docstring matches `func` in .sclpll
- Function file must be in `functions/` directory

**"Dependency not satisfied"**
- Check step IDs match exactly (case-sensitive)
- Check `@step id <- dep1, dep2` syntax

**"Parse error"**
- Check indentation (step body must be indented)
- Check for missing `@workflow` directive
- Check quoted strings have closing `"`

**Unicode errors on Windows**
- Use: `$env:PYTHONIOENCODING="utf-8"; python -X utf8 script.py`
- Or run in Windows Terminal (supports Unicode)

**Web GUI won't start (planned)**
- Ensure `fastapi` and `uvicorn` are installed: `pip install fastapi uvicorn`
- Check port 8000 is not in use: `netstat -ano | findstr :8000`
- Try a different port: `python -m app web --port 8080`

**Web GUI shows blank page (planned)**
- Clear browser cache
- Check browser console for JavaScript errors
- Verify the server is running: `curl http://localhost:8000/api/health`

**Browser doesn't open automatically (planned)**
- Manually navigate to `http://localhost:8000`
- Or set the `BROWSER` environment variable
