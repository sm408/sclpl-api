# SCLPLAPI

<p align="center">
  <code>S C L P L A P I</code><br>
  <strong>API Workflow Studio · Python-First · Local-First</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
</p>

---

SCLPLAPI is a programmable, local-first API workflow studio with Python-native extensibility.

| Role | What it does |
|------|-------------|
| **API Client** | Send HTTP requests with variable resolution |
| **Workflow Runner** | Chain steps with dependencies and parallelism |
| **Transformation Engine** | Process responses with Python functions |
| **Export Workbench** | Output results to JSON, CSV, or reports |

## Quick Start

```bash
# Clone and install
git clone https://github.com/sm408/sclpl-api.git && cd sclpl-api
pip install -e .

# Launch the TUI
python -m app
```

### Run an Example

```bash
python -m app.core.engine.sclpll_cli run examples/weather_pipeline/weather-pipeline.sclpll
```

## SCLPLL at a Glance

| Feature | Syntax |
|---------|--------|
| Define workflow | `@workflow id "Name"` |
| Set base URL | `@base_url https://api.example.com` |
| HTTP request | `@step id -> var` + `request GET url` |
| Python function | `@step id <- deps -> var` + `func Name` |
| Dependencies | `@step id <- dep1, dep2 -> var` |
| Parallel | Steps with no `<-` run in parallel |
| Loops | `@foreach {{collection}} as item` |
| Conditions | `@when {{var}} == value` |

## TUI Menu

```
[R] Run          Execute, validate, or re-run workflows
[S] Send         Send a single HTTP request
[C] Collections  Browse saved collections and requests
[H] History      Browse past request and workflow history
[M] Manage       Environments, functions, plugins, settings
[I] Tools        Import, export, and utilities
```

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — Backend architecture
- [docs/SCLPLL_LANGUAGE.md](docs/SCLPLL_LANGUAGE.md) — Language reference
- [docs/PLUGIN_SYSTEM.md](docs/PLUGIN_SYSTEM.md) — Plugin development
- [docs/WORKFLOW_ENGINE.md](docs/WORKFLOW_ENGINE.md) — Workflow engine

## Testing

```bash
pytest tests/ -v
```

## License

MIT
