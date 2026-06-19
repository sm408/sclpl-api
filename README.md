# SCLPLAPI

SCLPLAPI is a programmable, local-first API workflow studio with Python-native extensibility.

## What it is

SCLPLAPI sits between:

- an API client
- a workflow runner
- a lightweight transformation engine
- an export/reporting workbench

Core capabilities:

- **Request execution** — HTTP calls with variable resolution
- **Workflow orchestration** — sequential and parallel execution
- **SCLPLL scripting** — human-readable workflow definitions
- **Function system** — Python-native extensibility
- **Export pipelines** — JSON and CSV output

## Quick Start

```bash
# Install dependencies
pip install -e .

# Run an example
python -m app.core.engine.sclpll_cli run examples/financial_pipeline/script.sclpll

# Run tests
pytest tests/ -v
```

## SCLPLL Scripting Language

Define workflows in human-readable `.sclpll` files:

```sclpll
@workflow my-pipeline "My Pipeline"
    Fetches data and generates a report.

@base_url https://api.example.com

@step fetch_users -> users_data
    request GET {{base_url}}/users

@step fetch_posts -> posts_data
    request GET {{base_url}}/posts

@step analyze <- fetch_users, fetch_posts -> report
    func Analyze Data
```

Compile and run:

```bash
# Compile to workflow.json + run.py
python -m app.core.engine.sclpll_cli compile script.sclpll

# Run directly
python -m app.core.engine.sclpll_cli run script.sclpll
```

## Examples

| Example | Steps | API | Description |
|---------|-------|-----|-------------|
| [Weather Pipeline](examples/weather_pipeline/) | 5 | wttr.in | Fetch weather, extract 5AM data, export |
| [Job Tracker](examples/job_tracker_pipeline/) | 8 | JSONPlaceholder | Parallel fetch, merge, analyze, report |
| [Financial Pipeline](examples/financial_pipeline/) | 7 | CoinGecko | Crypto prices, market analysis |
| [Multi-Provider Aggregator](examples/multi_provider_aggregator/) | 7 | JSONPlaceholder | Parallel processing, aggregation |

## Architecture

```text
app/
  core/
    contracts/     ABC interfaces
    engine/        workflow engines, SCLPLL compiler
    models/        data models (request, workflow, context)
  services/
    request_executor.py    HTTP execution
    export_service.py      JSON/CSV export
    history_service.py     request history
  storage/
    db.py          SQLite persistence
  ui/
    app.py         composition root
    cli.py         Typer CLI (13+ commands)
functions/         Python extension functions
examples/          working pipeline examples
tests/             113 tests
docs/              comprehensive documentation
```

## Documentation

### By Perspective

- [User Guide](docs/perspectives/user/README.md) — quick start, patterns, troubleshooting
- [Developer Guide](docs/perspectives/developer/README.md) — architecture, extending, testing
- [Sales & Marketing](docs/perspectives/sales-marketing/README.md) — value proposition, use cases
- [Enthusiast Showcase](docs/perspectives/enthusiast-showcase/README.md) — advanced patterns

### Reference

- [SCLPLL Language](docs/SCLPLL_LANGUAGE.md) — scripting language reference
- [Architecture](ARCHITECTURE.md) — layered design
- [Workflow Engine](WORKFLOW_ENGINE.md) — runtime design
- [Function System](FUNCTION_SYSTEM.md) — extensibility layer
- [Features](FEATURES.md) — capability matrix

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_sclpll_compiler.py -v
```

**113 tests** covering:
- SCLPLL compiler (24 tests)
- Workflow engine (15 tests)
- Parallel workflow engine (12 tests)
- Function runner (10 tests)
- Auth system (15 tests)
- Event bus (4 tests)
- Variable resolver (6 tests)
- Models (3 tests)
- Database (5 tests)
- Export (3 tests)

## Build Doctrine

- **Local-first** — no mandatory cloud dependency
- **Human-hackable** — filesystem-visible configuration
- **Python-first** — prefer Python runtime over JS
- **Strict core** — disciplined engine and contracts
- **Runtime first** — execution before visual builders
