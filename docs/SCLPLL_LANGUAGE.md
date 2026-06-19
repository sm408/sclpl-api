# SCLPLL Script Language

**SCLPLL** (SCLPLAPI Language) is a human-readable scripting language for defining workflow pipelines. It compiles to `workflow.json` and `run.py`, and can be decompiled back.

## Quick Start

```bash
# Compile script.sclpll to workflow.json + run.py
python -m app.core.engine.sclpll_cli compile my_pipeline.sclpll

# Run directly from script.sclpll
python -m app.core.engine.sclpll_cli run my_pipeline.sclpll

# Decompile workflow.json back to script.sclpll
python -m app.core.engine.sclpll_cli decompile workflow.json

# Validate a script
python -m app.core.engine.sclpll_cli validate my_pipeline.sclpll
```

## Syntax Overview

### Directives

| Directive | Purpose | Example |
|-----------|---------|---------|
| `@workflow` | Define workflow identity | `@workflow my-pipeline "My Pipeline"` |
| `@base_url` | Set base URL for all requests | `@base_url https://api.example.com` |
| `@var` | Define a variable | `@var city = NewYork` |
| `@step` | Define a workflow step | `@step fetch_data -> data` |

### Step Types

#### Request Steps (HTTP calls)

```sclpll
@step fetch_users -> users_data
    request GET {{base_url}}/users
    header Accept: application/json
```

#### Function Steps (Python functions)

```sclpll
@step merge_data <- fetch_users, fetch_posts -> merged
    func Merge User Posts
```

### Dependencies

Use `<-` to declare dependencies. Steps without dependencies run in parallel.

```sclpll
# Independent (runs in parallel)
@step fetch_users -> users_data
    request GET {{base_url}}/users

# Depends on fetch_users
@step process_users <- fetch_users -> processed
    func Process Users

# Depends on multiple steps
@step merge <- fetch_users, fetch_posts -> merged
    func Merge Data
```

### Output Variables

Use `->` to declare output variables. These become available as `{{var_name}}` in downstream steps.

```sclpll
@step fetch_data -> raw_data
    request GET {{base_url}}/data
```

### Variables

```sclpll
@base_url https://api.example.com
@var api_key = sk-abc123
@var timeout = 30
```

Reference variables with `{{variable_name}}`:

```sclpll
@step auth_request -> response
    request GET {{base_url}}/protected
    header Authorization: Bearer {{api_key}}
```

### Comments

```sclpll
# This is a comment
@step fetch_data -> data  # Comments must be on their own line
    request GET {{base_url}}/data
```

## Complete Example

```sclpll
# Financial Market Analysis Pipeline
# Fetches crypto prices and market data in parallel

@workflow financial-analysis "Financial Market Analysis"
    Fetches cryptocurrency prices and market data in parallel,
    merges results, and generates a comprehensive report.

@base_url https://api.coingecko.com/api/v3

# Phase 1: Independent fetches (run in parallel)
@step fetch_bitcoin -> bitcoin_data
    request GET {{base_url}}/simple/price?ids=bitcoin&vs_currencies=usd

@step fetch_ethereum -> ethereum_data
    request GET {{base_url}}/simple/price?ids=ethereum&vs_currencies=usd

# Phase 2: Processing (waits for dependencies)
@step merge_prices <- fetch_bitcoin, fetch_ethereum -> merged_prices
    func Merge Crypto Prices

# Phase 3: Final report
@step generate_report <- merge_prices -> final_report
    func Generate Financial Report
```

## Compilation

### To workflow.json

```bash
python -m app.core.engine.sclpll_cli compile script.sclpll
```

Generates:
- `workflow.json` - Workflow definition
- `run.py` - Python runner script

### From workflow.json (Decompilation)

```bash
python -m app.core.engine.sclpll_cli decompile workflow.json
```

Generates `workflow.sclpll` (or specify with `--output`).

## CLI Commands

| Command | Description |
|---------|-------------|
| `compile <file.sclpll>` | Compile to workflow.json + run.py |
| `decompile <workflow.json>` | Decompile to script.sclpll |
| `validate <file.sclpll>` | Validate syntax |
| `run <file.sclpll>` | Compile and execute |

### Options

- `--output-dir <dir>` - Output directory for compile
- `--output <file>` - Output file for decompile

## Parallel Execution

Steps without dependencies automatically run in parallel:

```sclpll
# These 4 steps run concurrently
@step fetch_users -> users_data
    request GET {{base_url}}/users

@step fetch_posts -> posts_data
    request GET {{base_url}}/posts

@step fetch_comments -> comments_data
    request GET {{base_url}}/comments

# This waits for all 3 to complete
@step analyze <- fetch_users, fetch_posts, fetch_comments -> analysis
    func Analyze All Data
```

## Mapping to workflow.json

| SCLPLL | workflow.json |
|--------|---------------|
| `@workflow id "name"` | `"id": "id", "name": "name"` |
| `@base_url URL` | `"variables": {"base_url": "URL"}`
| `@var k = v` | `"variables": {"k": "v"}`
| `@step id -> var` | `"id": "id", "output_variable": "var"` |
| `@step id <- dep1, dep2` | `"depends_on": ["dep1", "dep2"]` |
| `request GET url` | `"type": "request", "config": {"inline_request": {"method": "GET", "url": "url"}}` |
| `func Name` | `"type": "function", "config": {"function_name": "Name"}` |
| `header K: V` | `"headers": {"K": "V"}` |
| `body {...}` | `"body": "{...}"` |
