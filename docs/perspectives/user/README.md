# SCLPLAPI User Guide

Welcome to SCLPLAPI — a local-first, Python-first API workflow studio. This guide walks you through building, running, and extending API workflows from scratch.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Core Concepts](#core-concepts)
3. [Writing SCLPLL Scripts](#writing-sclpll-scripts)
4. [Running Workflows](#running-workflows)
5. [Variables and Dependencies](#variables-and-dependencies)
6. [Custom Functions](#custom-functions)
7. [Common Patterns and Recipes](#common-patterns-and-recipes)
8. [CLI Reference](#cli-reference)
9. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Installation

```bash
git clone https://github.com/your-org/sclpl-api.git
cd sclpl-api
pip install -e .
```

### Your First Pipeline in 60 Seconds

Create a file called `hello.sclpll`:

```sclpll
@workflow hello-api "Hello API Pipeline"
    A simple pipeline that fetches a public API endpoint.

@base_url https://jsonplaceholder.typicode.com

@step fetch_users -> users_data
    request GET {{base_url}}/users

@step extract_names <- fetch_users -> names
    func Extract User Names
```

Run it:

```bash
python -m app.core.engine.sclpll_cli run hello.sclpll
```

That's it — two steps, one dependency, zero config files.

---

## Core Concepts

### The SCLPLAPI Mental Model

SCLPLAPI sits between four roles:

| Role | What it does |
|------|-------------|
| **API Client** | Send HTTP requests with variable resolution |
| **Workflow Runner** | Chain steps with dependencies and parallelism |
| **Transformation Engine** | Process responses with Python functions |
| **Export Workbench** | Output results to JSON, CSV, or reports |

### Key Terms

| Term | Meaning |
|------|---------|
| **Workflow** | A named pipeline of steps with dependencies |
| **Step** | A single unit of work (request, function, or export) |
| **Node** | A step in the execution graph |
| **Edge** | A dependency link between steps |
| **Context (`ctx`)** | Shared execution state passed between steps |
| **Variable** | A named value resolved at runtime with `{{name}}` syntax |

---

## Writing SCLPLL Scripts

SCLPLL (SCLPLAPI Language) is a human-readable scripting language for defining workflows. It compiles to `workflow.json` and `run.py`, and can be decompiled back.

### Directives Reference

| Directive | Purpose | Example |
|-----------|---------|---------|
| `@workflow` | Define workflow identity | `@workflow my-pipeline "My Pipeline"` |
| `@base_url` | Set base URL for requests | `@base_url https://api.example.com` |
| `@var` | Define a variable | `@var city = NewYork` |
| `@step` | Define a workflow step | `@step fetch_data -> data` |

### Step Types

#### Request Steps (HTTP calls)

```sclpll
@step fetch_users -> users_data
    request GET {{base_url}}/users
    header Accept: application/json
    header Authorization: Bearer {{api_key}}
```

Supported methods: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`.

#### Function Steps (Python functions)

```sclpll
@step merge_data <- fetch_users, fetch_posts -> merged
    func Merge User Posts
```

The `func` keyword references a Python function by its `@name` metadata.

### Comments

```sclpll
# Full-line comments are supported
@step fetch_data -> data  # Inline comments work too
    request GET {{base_url}}/data
```

### Complete Script Example

```sclpll
# Financial Market Analysis Pipeline
# Fetches crypto prices in parallel, merges, and reports

@workflow financial-analysis "Financial Market Analysis"
    Fetches cryptocurrency prices and market data in parallel,
    merges results, and generates a comprehensive report.

@base_url https://api.coingecko.com/api/v3

# Phase 1: Independent fetches (run in parallel)
@step fetch_bitcoin -> bitcoin_data
    request GET {{base_url}}/simple/price?ids=bitcoin&vs_currencies=usd

@step fetch_ethereum -> ethereum_data
    request GET {{base_url}}/simple/price?ids=ethereum&vs_currencies=usd

@step fetch_solana -> solana_data
    request GET {{base_url}}/simple/price?ids=solana&vs_currencies=usd

# Phase 2: Processing (waits for dependencies)
@step merge_prices <- fetch_bitcoin, fetch_ethereum, fetch_solana -> merged_prices
    func Merge Crypto Prices

# Phase 3: Final report
@step generate_report <- merge_prices -> final_report
    func Generate Financial Report
```

---

## Running Workflows

### From a SCLPLL Script

```bash
# Compile to workflow.json + run.py
python -m app.core.engine.sclpll_cli compile my_pipeline.sclpll

# Run directly
python -m app.core.engine.sclpll_cli run my_pipeline.sclpll

# Validate syntax without running
python -m app.core.engine.sclpll_cli validate my_pipeline.sclpll
```

### From a workflow.json

```bash
# Run pre-compiled workflow
python examples/weather_pipeline/run.py
```

### From the CLI

```bash
# List available workflows
sclpl workflow list

# Run a saved workflow
sclpl workflow run my-pipeline

# Run with variable overrides
sclpl workflow run my-pipeline --var city=London --var api_key=sk-abc123
```

### Compilation Output

When you compile a `.sclpll` file, two artifacts are generated:

| File | Purpose |
|------|---------|
| `workflow.json` | Machine-readable workflow definition |
| `run.py` | Standalone Python runner script |

---

## Variables and Dependencies

### Defining Variables

```sclpll
@base_url https://api.example.com
@var api_key = sk-abc123
@var timeout = 30
@var city = NewYork
```

### Using Variables

Reference variables with `{{variable_name}}` syntax anywhere in URLs, headers, or bodies:

```sclpll
@step fetch_weather -> weather_data
    request GET {{base_url}}/weather?q={{city}}&appid={{api_key}}
```

### Variable Precedence

When the same variable name exists in multiple scopes, resolution follows this order (highest priority first):

1. Step-level override
2. Runtime value (set by a function)
3. Batch row (CSV-driven execution)
4. Workflow-level definition
5. Environment value
6. Global default

### Output Variables

Steps declare output variables with `->`. Downstream steps reference them:

```sclpll
@step fetch_data -> raw_data
    request GET {{base_url}}/data

@step process <- fetch_data -> processed
    func Process Data
```

The function `Process Data` receives `raw_data` in its execution context.

### Dependency Declaration

Use `<-` to declare what a step depends on:

```sclpll
# No dependencies — runs in parallel with other independent steps
@step fetch_users -> users_data
    request GET {{base_url}}/users

# Depends on one step
@step process_users <- fetch_users -> processed
    func Process Users

# Depends on multiple steps
@step merge <- fetch_users, fetch_posts -> merged
    func Merge Data
```

**Key rule**: Steps without dependencies run in parallel. Steps with dependencies wait for all upstream steps to complete.

---

## Custom Functions

### Function Contract

Every function is a Python file with a docstring header and a `run(ctx)` entry point:

```python
"""
@name: Extract User Names
@type: post_response
@version: 1
"""

def run(ctx):
    users = ctx.response.json()
    names = [u["name"] for u in users]
    ctx.workflow_variables["user_names"] = names
    return ctx
```

### Function Types

| Type | When it runs | Use case |
|------|-------------|----------|
| `pre_request` | Before HTTP call | Add auth headers, sign requests |
| `post_response` | After HTTP call | Transform data, extract fields |
| `auth_token` | On auth challenge | Generate/refresh tokens |
| `transformer` | In pipeline | Map, filter, merge data |
| `exporter` | At pipeline end | Write output files |

### Execution Context (`ctx`)

The `ctx` object provides access to everything a function needs:

| Attribute | Type | Description |
|-----------|------|-------------|
| `ctx.request` | dict | Current request details |
| `ctx.response` | object | HTTP response (with `.json()`, `.text`, `.status_code`) |
| `ctx.workflow` | dict | Workflow metadata |
| `ctx.environment` | dict | Current environment variables |
| `ctx.workflow_variables` | dict | Shared variable store (read/write) |
| `ctx.runtime` | dict | Runtime execution state |
| `ctx.config` | dict | Step configuration |
| `ctx.metadata` | dict | Step metadata |
| `ctx.batch_row` | dict | Current CSV row (if batch execution) |

### Where to Put Functions

Functions are discovered from the `functions/` directory tree:

```
functions/
  transformers/
    extract_date.py
    extract_weather.py
    merge_data.py
  exporters/
    export_csv.py
    export_json.py
  auth/
    bearer_token.py
```

SCLPLAPI recursively scans this directory and registers every function that has the correct docstring header.

### Writing a Merge Function

```python
"""
@name: Merge Crypto Prices
@type: transformer
@version: 1
"""

def run(ctx):
    bitcoin = ctx.runtime.get("fetch_bitcoin", {})
    ethereum = ctx.runtime.get("fetch_ethereum", {})
    solana = ctx.runtime.get("fetch_solana", {})

    merged = {
        "bitcoin_usd": bitcoin.get("bitcoin", {}).get("usd", 0),
        "ethereum_usd": ethereum.get("ethereum", {}).get("usd", 0),
        "solana_usd": solana.get("solana", {}).get("usd", 0),
        "timestamp": ctx.metadata.get("execution_time", ""),
    }

    ctx.workflow_variables["merged_prices"] = merged
    return ctx
```

### Writing an Export Function

```python
"""
@name: Export Weather Data
@type: exporter
@version: 1
"""

import json
import csv
from pathlib import Path

def run(ctx):
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    data = {
        "date": ctx.workflow_variables.get("today"),
        "city": ctx.workflow_variables.get("city"),
        "temperature": ctx.workflow_variables.get("weatherAt5AM_tempC"),
        "description": ctx.workflow_variables.get("weatherAt5AM_desc"),
    }

    with open(output_dir / "weather_at_5am.json", "w") as f:
        json.dump(data, f, indent=2)

    with open(output_dir / "weather_at_5am.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=data.keys())
        writer.writeheader()
        writer.writerow(data)

    return ctx
```

---

## Common Patterns and Recipes

### Pattern 1: Sequential Data Pipeline

Fetch → Transform → Export:

```sclpll
@workflow sequential-demo "Sequential Pipeline"

@step fetch -> raw
    request GET https://api.example.com/data

@step transform <- raw -> cleaned
    func Clean Data

@step export <- cleaned -> output
    func Export CSV
```

### Pattern 2: Parallel Fan-Out / Fan-In

Fetch multiple sources in parallel, then merge:

```sclpll
@workflow parallel-demo "Parallel Fan-Out Fan-In"

@step fetch_a -> data_a
    request GET https://api-a.com/data

@step fetch_b -> data_b
    request GET https://api-b.com/data

@step fetch_c -> data_c
    request GET https://api-c.com/data

@step merge <- fetch_a, fetch_b, fetch_c -> combined
    func Merge All Sources
```

### Pattern 3: Chained Variable Resolution

Each step sets variables the next step needs:

```sclpll
@workflow chained-vars "Chained Variable Resolution"

@var city = London

@step get_weather -> weather_raw
    request GET https://wttr.in/{{city}}?format=j1

@step extract_date <- get_weather -> date_info
    func Extract Date

@step get_hourly <- extract_date -> hourly
    request GET https://wttr.in/{{city}}?format=j1

@step extract_5am <- hourly -> report
    func Extract 5AM Weather
```

### Pattern 4: CSV Batch Execution

Run the same workflow for each row in a CSV:

```bash
sclpl workflow run my-pipeline --batch input.csv
```

Each row becomes `ctx.batch_row`, and the workflow runs once per row.

### Pattern 5: Environment Switching

Define environments and switch at runtime:

```bash
# Use development environment
sclpl workflow run my-pipeline --env development

# Use production environment
sclpl workflow run my-pipeline --env production
```

---

## CLI Reference

### SCLPLL Commands

| Command | Description |
|---------|-------------|
| `compile <file.sclpll>` | Compile to workflow.json + run.py |
| `decompile <workflow.json>` | Decompile back to script.sclpll |
| `validate <file.sclpll>` | Validate syntax without running |
| `run <file.sclpll>` | Compile and execute immediately |

### Options

| Option | Description |
|--------|-------------|
| `--output-dir <dir>` | Output directory for compile |
| `--output <file>` | Output file for decompile |
| `--var key=value` | Override a variable at runtime |
| `--env <name>` | Select an environment |
| `--batch <file.csv>` | Run for each CSV row |

### Workflow Management

| Command | Description |
|---------|-------------|
| `sclpl workflow list` | List saved workflows |
| `sclpl workflow run <name>` | Run a saved workflow |
| `sclpl workflow show <name>` | Show workflow details |
| `sclpl workflow delete <name>` | Delete a saved workflow |

---

## Troubleshooting

### Common Issues

| Problem | Cause | Solution |
|---------|-------|----------|
| `Variable not found` | Variable not defined or misspelled | Check `@var` declarations and `{{name}}` spelling |
| `Function not found` | Function not in `functions/` tree | Verify file exists and has correct `@name` in docstring |
| `Dependency not resolved` | Step depends on a non-existent step | Check `<-` references match actual step IDs |
| `Step timeout` | API call exceeded timeout | Increase timeout or add retry logic |
| `Import error in function` | Missing dependency in function file | Install the required package |
| `Decompile mismatch` | workflow.json was hand-edited | Re-compile from original `.sclpll` |

### Debug Mode

Run with verbose output to see execution details:

```bash
python -m app.core.engine.sclpll_cli run my_pipeline.sclpll --verbose
```

### Checking Compiled Output

If a workflow behaves unexpectedly, inspect the compiled artifacts:

```bash
# Compile without running
python -m app.core.engine.sclpll_cli compile my_pipeline.sclpll

# Inspect the generated workflow.json
cat workflow.json

# Inspect the generated runner
cat run.py
```

### Function Debugging

Add logging to your functions:

```python
"""
@name: Debug Example
@type: post_response
@version: 1
"""

import logging
logger = logging.getLogger(__name__)

def run(ctx):
    logger.info(f"Response status: {ctx.response.status_code}")
    logger.info(f"Response body: {ctx.response.text[:200]}")
    logger.info(f"Workflow vars: {ctx.workflow_variables}")
    return ctx
```

---

## Next Steps

- **Examples**: Explore `examples/` for working pipelines (weather, job tracker, financial)
- **Advanced Workflows**: Read the [Workflow Engine documentation](../../../WORKFLOW_ENGINE.md)
- **Function System**: Deep dive into [FUNCTION_SYSTEM.md](../../../FUNCTION_SYSTEM.md)
- **Export Engine**: Learn about export pipelines in [EXPORT_ENGINE.md](../../../EXPORT_ENGINE.md)
- **Developer Guide**: Want to contribute? See the [Developer Perspective](../developer/README.md)
