# SCLPLAPI Cheatsheet

> One-page reference. Print this and keep it next to your terminal.

---

## CLI Commands

```bash
python -m app tui                                          # Interactive TUI
python -m app.core.engine.sclpll_cli run script.sclpll     # Run a workflow
python -m app.core.engine.sclpll_cli compile script.sclpll # Compile to JSON + Python
python -m app.core.engine.sclpll_cli validate script.sclpll # Check syntax
python -m app.core.engine.sclpll_cli decompile workflow.json # Back to .sclpll
python -m app run URL                                      # Single HTTP request
python -m app batch data.csv URL                           # Batch requests from CSV
python -m app functions                                    # List discovered functions
python -m app history list                                 # Show request history
python -m app env list                                     # List environments
python -m app env create NAME                              # Create environment
python -m app env set-var ENV KEY=VALUE                    # Set variable
python -m app env activate NAME                            # Activate environment
python -m app export --format json --output out.json       # Export history
python -m app workflow file.json                           # Run compiled workflow
pytest tests/ -v                                           # Run tests
```

---

## SCLPLL Syntax

### Structure

```sclpll
@workflow <id> "<name>"
    Description text.

@base_url <url>
@var <name> = <value>

@step <id> -> <output_var>
    request <METHOD> <url>
    header <Key>: <Value>

@step <id> <- <dep1>, <dep2> -> <output_var>
    func <Function Name>
```

### Directives

| Directive | Purpose | Example |
|-----------|---------|---------|
| `@workflow` | Define workflow | `@workflow my-id "My Pipeline"` |
| `@base_url` | Base URL | `@base_url https://api.example.com` |
| `@var` | Variable | `@var api_key = sk-123` |
| `@step` | Step definition | `@step fetch -> data` |

### Step Types

```sclpll
# HTTP request
@step fetch_data -> output
    request GET {{base_url}}/data
    header Accept: application/json
    header Authorization: Bearer {{api_key}}

# Python function
@step process <- fetch_data -> result
    func Process Data
```

### Dependencies

```sclpll
@step a -> data_a              # No deps = runs in parallel
@step b -> data_b              # No deps = runs in parallel
@step c <- a, b -> combined    # Waits for a AND b
```

### Variables

```sclpll
@var city = London
@step get -> data
    request GET https://api.example.com?q={{city}}
```

**Nested JSON access:** `{{step_name.field.subfield}}`
**List access:** `{{step_name.items[0]}}`

### Loops

```sclpll
# foreach
@step process_each <- fetch_users -> processed
    @foreach {{fetch_users.body}} as user
    func Process Single User

# repeat
@step batch -> results
    @repeat 5
    request GET {{base_url}}/items/{{_index}}
```

### Conditions

```sclpll
@step success_path <- check
    @when {{check.status_code}} == 200
    request GET {{base_url}}/data
```

### Rate Limiting

```sclpll
@step slow_api -> data
    @semaphore 2
    request GET {{base_url}}/slow
```

---

## Function Contract

```python
"""
@name: My Function
@type: transformer
@version: 1
"""

def run(ctx):
    # Access step outputs
    data = ctx.step_outputs.get("step_id", {})

    # Access variables
    city = ctx.workflow_variables.get("city")

    # Set variables for downstream
    ctx.workflow_variables["result"] = processed_data

    # Access environment
    env = ctx.environment

    # Access request/response
    req = ctx.request
    resp = ctx.response

    return ctx
```

### Function Types

| Type | When | Use |
|------|------|-----|
| `transformer` | Pipeline step | Map, filter, merge |
| `exporter` | Pipeline end | Write files |
| `pre_request` | Before HTTP | Add headers |
| `post_response` | After HTTP | Transform data |
| `auth_token` | Auth challenge | Generate tokens |

### Context Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `ctx.step_outputs` | dict | Previous step outputs |
| `ctx.workflow_variables` | dict | Shared variable store |
| `ctx.environment` | dict | Environment variables |
| `ctx.request` | dict | Current request |
| `ctx.response` | object | HTTP response |
| `ctx.metadata` | dict | Execution metadata |
| `ctx.batch_row` | dict | Current CSV row |
| `ctx.runtime` | dict | Runtime state |
| `ctx.config` | dict | Step config |

---

## Common Patterns

### Sequential Pipeline

```sclpll
@step fetch -> raw
    request GET {{base_url}}/data
@step clean <- raw -> clean
    func Clean Data
@step export <- clean -> out
    func Export CSV
```

### Parallel Fan-Out / Fan-In

```sclpll
@step a -> da
    request GET {{base_url}}/a
@step b -> db
    request GET {{base_url}}/b
@step merge <- a, b -> combined
    func Merge
```

### Chained Variables

```sclpll
@var city = London
@step weather -> raw
    request GET https://wttr.in/{{city}}?format=j1
@step extract <- raw -> temp
    func Extract Temp
@step report <- temp -> final
    request GET {{base_url}}/report?temp={{temp}}
```

### Authenticated Request

```sclpll
@step protected -> data
    request GET {{base_url}}/protected
    header Authorization: Bearer {{api_key}}
```

---

## HTTP Methods

| Method | CLI Example |
|--------|------------|
| GET | `python -m app run https://api.example.com/data` |
| POST | `python -m app run URL -m POST -b '{"key":"val"}'` |
| PUT | `python -m app run URL -m PUT -b '{"key":"val"}'` |
| PATCH | `python -m app run URL -m PATCH -b '{"key":"val"}'` |
| DELETE | `python -m app run URL -m DELETE` |

### Auth Options

```bash
# Bearer token
python -m app run URL --auth-type bearer --auth-token sk-123

# Basic auth
python -m app run URL --auth-type basic --auth-user admin --auth-pass secret

# API key
python -m app run URL --auth-type api_key --auth-key mykey --auth-header X-API-Key
```

---

## File Extensions

| Extension | Purpose |
|-----------|---------|
| `.sclpll` | Human-readable workflow script |
| `.json` | Compiled workflow definition |
| `.py` | Custom function or runner |

---

## Quick Troubleshooting

| Problem | Quick Fix |
|---------|-----------|
| Unicode error on Windows | `$env:PYTHONIOENCODING="utf-8"` |
| Function not found | Check `@name` matches exactly |
| Variable not resolved | Check `@var` or environment |
| Dependency error | Check step IDs match |
| Parse error | Check indentation and syntax |
