# SCLPLAPI

<p align="center">
  <code>S C L P L A P I</code><br>
  <strong>API Workflow Studio &middot; Python-First &middot; Local-First</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/tests-113%20passing-brightgreen?logo=pytest&logoColor=white" alt="Tests">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/status-alpha-orange" alt="Status">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
</p>

---

SCLPLAPI is a programmable, local-first API workflow studio with Python-native extensibility.

It sits between four roles:

| Role | What it does |
|------|-------------|
| **API Client** | Send HTTP requests with variable resolution |
| **Workflow Runner** | Chain steps with dependencies and parallelism |
| **Transformation Engine** | Process responses with Python functions |
| **Export Workbench** | Output results to JSON, CSV, or reports |

## Quick Start

```bash
# Install
git clone https://github.com/sm408/sclpl-api.git && cd sclpl-api

# Core only (TUI + CLI)
pip install -e .

# With Web GUI
pip install -e ".[web]"

# With Excel export
pip install -e ".[excel]"

# Everything
pip install -e ".[all]"

# Run the interactive TUI
python -m app tui

# Or start the Web GUI (requires [web] extra)
sclplapi web

# Or run an example pipeline directly
python -m app.core.engine.sclpll_cli run examples/financial_pipeline/script.sclpll
```

That's it. Three commands to a running workflow.

### Dependencies

| Component | Packages |
|-----------|----------|
| Core | `httpx`, `typer`, `rich`, `pydantic` |
| Web GUI *(planned)* | `fastapi`, `uvicorn`, `jinja2` |

## What's New

- **v0.2.0** — Web GUI *(planned)*
  - Browser-based request editor with method selector
  - Collections management and workflow execution
  - Flow builder with visual node canvas
  - History viewer with color-coded methods and statuses
  - Settings panel with theme support

- **v0.1.0** — Initial release
  - SCLPLL scripting language with compiler/decompiler
  - Parallel workflow engine with dependency graph resolution
  - Python-native function system with filesystem discovery
  - Rich TUI with live workflow execution
  - JSON/CSV export pipelines
  - 113 passing tests

## See It in Action

### Terminal UI (Implemented)

**Run a workflow from the TUI:**

```
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║   ███████╗ ██████╗██╗     ██████╗ ██╗      █████╗ ██████╗ ██╗   ║
║   ██╔════╝██╔════╝██║     ██╔══██╗██║     ██╔══██╗██╔══██╗██║   ║
║   ███████╗██║     ██║     ██████╔╝██║     ███████║██████╔╝██║   ║
║   ╚════██║██║     ██║     ██╔═══╝ ██║     ██╔══██║██╔══██╗██║   ║
║   ███████║╚██████╗███████╗██║     ███████╗██║  ██║██║  ██║██║   ║
║   ╚══════╝ ╚═════╝╚══════╝╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝   ║
║                                                                   ║
║       API Workflow Studio  ·  Python-First  ·  Local-First       ║
╚═══════════════════════════════════════════════════════════════════╝

┌──────────────────── Main Menu ────────────────────┐
│  [R]  Run Workflow   [L]  Load Script             │
│  [F]  Functions      [H]  History                 │
│  [E]  Environments   [V]  Validate                │
│  [Q]  Quit                                        │
└───────────────────────────────────────────────────┘
```

### Web GUI (Planned)

**Browser-based interface with sidebar navigation:**

```
┌──────────────────────────────────────────────────────────────────────┐
│  SCLPLAPI                                    ┌─────────────────────┐ │
├──────────────┬───────────────────────────────┤  Request Editor     │ │
│              │                               │                     │ │
│  Home        │  GET  [https://api.example.com│  Params  Headers    │ │
│  Request     │                               │  Body               │ │
│  Editor      │  ─────────────────────────────│                     │ │
│  Collections │  Response                     │  [Send]             │ │
│  Workflows   │  Status: 200  Time: 142ms     │                     │ │
│  Flow        │  Size: 1.2KB                  │                     │ │
│  Builder     │                               │                     │ │
│  Functions   │  { "users": [...] }           │                     │ │
│  History     │                               │                     │ │
│  Settings    │                               │                     │ │
│              │                               │                     │ │
└──────────────┴───────────────────────────────┴─────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

**Write a workflow in SCLPLL:**

```sclpll
@workflow financial-analysis "Financial Market Analysis"
    Fetches crypto prices in parallel and generates a report.

@base_url https://api.coingecko.com/api/v3

@step fetch_bitcoin -> bitcoin_data
    request GET {{base_url}}/simple/price?ids=bitcoin&vs_currencies=usd

@step fetch_ethereum -> ethereum_data
    request GET {{base_url}}/simple/price?ids=ethereum&vs_currencies=usd

@step merge <- fetch_bitcoin, fetch_ethereum -> merged
    func Merge Crypto Prices

@step report <- merge -> final_report
    func Generate Financial Report
```

**Output:**

```
══════════════════════════════════════════
  Financial Market Analysis
══════════════════════════════════════════

  ● fetch_bitcoin   448ms   HTTP 200
  ● fetch_ethereum  400ms   HTTP 200
  ● merge           5ms     ok
  ● report          3ms     ok

══════════════════════════════════════════
  PASSED in 653ms
══════════════════════════════════════════
```

## SCLPLL at a Glance

| Feature | Syntax |
|---------|--------|
| Define workflow | `@workflow id "Name"` |
| Set base URL | `@base_url https://api.example.com` |
| Define variable | `@var key = value` |
| HTTP request | `@step id -> var` + `request GET url` |
| Python function | `@step id <- deps -> var` + `func Name` |
| Dependencies | `@step id <- dep1, dep2 -> var` |
| Parallel | Steps with no `<-` run in parallel |
| Loops | `@foreach {{collection}} as item` |
| Conditions | `@when {{var}} == value` |

## Examples

| Example | Steps | API | Description |
|---------|-------|-----|-------------|
| [Weather Pipeline](examples/weather_pipeline/) | 5 | wttr.in | Fetch weather, extract 5AM data, export |
| [Job Tracker](examples/job_tracker_pipeline/) | 8 | JSONPlaceholder | Parallel fetch, merge, analyze, report |
| [Financial Pipeline](examples/financial_pipeline/) | 7 | CoinGecko | Crypto prices, market analysis |
| [Multi-Provider Aggregator](examples/multi_provider_aggregator/) | 7 | JSONPlaceholder | Parallel processing, aggregation |
| [Advanced Logic](examples/advanced_logic/) | — | — | Loops, conditions, semaphores, dot notation |
| [E-Commerce API](examples/ecommerce-api/) | 6 | JSONPlaceholder | Products, orders, payments, inventory, receipts |
| [Social Media Monitor](examples/social-media-monitor/) | 4 | JSONPlaceholder | Fetch posts, sentiment analysis, monitoring report |
| [Weather Dashboard](examples/weather-dashboard/) | 4 | wttr.in | Current weather, forecast, alerts, dashboard |

Run any example:

```bash
python -m app.core.engine.sclpll_cli run examples/financial_pipeline/financial-pipeline.sclpll
```

## Boilerplates

Ready-to-use workflow templates. Copy a boilerplate and customize it for your use case.

| Boilerplate | Description | Files |
|-------------|-------------|-------|
| [Minimal](boilerplates/minimal/) | Bare-bones workflow starter | 1 request step + 1 function step |
| [API Test](boilerplates/api-test/) | API endpoint testing with validation | Parallel requests + response validation |
| [Data Pipeline](boilerplates/data-pipeline/) | Extract, transform, load pipeline | 3 fetches + transform + load stages |

### Using a Boilerplate

```bash
# Copy a boilerplate to your working directory
cp -r boilerplates/minimal/ my-workflow/

# Edit the workflow
# - Update workflow name and description in minimal.sclpll
# - Change the base_url and endpoints
# - Modify functions/process.py with your logic

# Run it
python my-workflow/run.py
```

## Architecture

```text
app/
  core/
    contracts/     ABC interfaces (RequestExecutor, FunctionRunner, EventBus)
    engine/        Workflow engines, SCLPLL compiler, parallel executor
    models/        Data models (Request, Workflow, Context, Environment)
  services/
    request_executor.py    HTTP execution (httpx-based)
    export_service.py      JSON/CSV/Excel export
    history_service.py     Request history (SQLite)
  storage/
    db.py          SQLite persistence with migrations
  ui/
    app.py         Composition root
    cli.py         Typer CLI (13+ commands)
    tui.py         Rich-based Terminal UI
    logo.py        ASCII art branding
    web.py         FastAPI Web GUI (planned)
functions/         Python extension functions
examples/          Working pipeline examples
tests/             113 tests
docs/              Comprehensive documentation
```

**Layer direction:** `ui → services → core → storage`

## Documentation

### Getting Started

- **[ONBOARDING.md](ONBOARDING.md)** — Step-by-step tutorial (0-20 minutes)
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** — Common issues and solutions
- **[docs/CHEATSHEET.md](docs/CHEATSHEET.md)** — One-page reference card

### By Perspective

- [User Guide](docs/perspectives/user/README.md) — Quick start, patterns, recipes
- [Developer Guide](docs/perspectives/developer/README.md) — Architecture, extending, testing
- [Sales & Marketing](docs/perspectives/sales-marketing/README.md) — Value proposition, use cases
- [Enthusiast Showcase](docs/perspectives/enthusiast-showcase/README.md) — Advanced patterns

### Reference

| Document | Covers |
|----------|--------|
| [SCLPLL Language](docs/SCLPLL_LANGUAGE.md) | Scripting language reference |
| [Error Catalog](docs/ERROR_CATALOG.md) | Every error, its cause, and its fix |
| [Architecture](ARCHITECTURE.md) | Layered design |
| [Workflow Engine](WORKFLOW_ENGINE.md) | Runtime design |
| [Function System](FUNCTION_SYSTEM.md) | Extensibility layer |
| [Features](FEATURES.md) | Capability matrix |

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run a specific test file
pytest tests/test_sclpll_compiler.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=term-missing
```

**113 tests** covering:

| Module | Tests |
|--------|-------|
| SCLPLL compiler | 24 |
| Workflow engine | 15 |
| Parallel workflow engine | 12 |
| Function runner | 10 |
| Auth system | 15 |
| Event bus | 4 |
| Variable resolver | 6 |
| Models | 3 |
| Database | 5 |
| Export | 3 |

## Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Write tests for your changes
4. Run the test suite: `pytest tests/ -v`
5. Submit a pull request

See [CODING_STANDARDS.md](CODING_STANDARDS.md) for code style guidelines.

## Build Doctrine

- **Local-first** — No mandatory cloud dependency. Your data stays on your machine.
- **Human-hackable** — Filesystem-visible configuration. Edit `.sclpll` files in any text editor.
- **Python-first** — Prefer Python runtime and extension design over JS-heavy architecture.
- **Strict core** — Disciplined engine and contracts. Flexible feature layer.
- **Runtime first** — Execution and workflow integrity before visual workflow builders.

## License

MIT
