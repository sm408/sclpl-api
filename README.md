# SCLPLAPI

<p align="center">
  <code>S C L P L A P I</code><br>
  <strong>API Workflow Studio · Python-First · Local-First</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/tests-392%20passing-brightgreen?logo=pytest&logoColor=white" alt="Tests">
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
| **Live Monitor** | Watch APIs in background, get notified on events |
| **Export Workbench** | Output results to JSON, CSV, or reports |

## Quick Start

```bash
# Clone and install
git clone https://github.com/sm408/sclpl-api.git && cd sclpl-api
pip install -e .

# Launch the TUI
python -m app

# Or double-click sclplapi.bat (Windows) / ./sclplapi.sh (Linux/macOS)
```

### Run an Example

```bash
python -m app.core.engine.sclpll_cli run examples/weather_pipeline/weather-pipeline.sclpll
```

## Features

### Textual TUI

Modern terminal interface built with Textual:

- **Keyboard-first** — Ctrl+P command palette, Ctrl+T/R/W shortcuts
- **Panel layout** — Sidebar, workspace tabs, status bar
- **12 tabs** — Request, Collections, History, Workflows, Environments, Functions, Plugins, Monitors, Batch, Import/Export, Diff, Logs, Settings

### Live API Monitor

Watch APIs in the background while you work:

```
[Monitors] tab → New → Enter URL, interval, condition → Start
Continue working... → Notification when condition met
```

Conditions: `status == 200`, `body.price > 100`, `body.status == "active"`

### SCLPLL Scripting

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

### TUI Shortcuts

| Key | Action |
|-----|--------|
| Ctrl+P | Command Palette |
| Ctrl+T | New Request |
| Ctrl+R | Run Request |
| Ctrl+W | Close Tab |
| Ctrl+B | Batch Mode |
| Ctrl+M | Monitors |
| F1 | Help |
| F2 | Toggle Theme |
| F5 | Refresh |

## Examples

| Example | Steps | Description |
|---------|-------|-------------|
| [Weather Pipeline](examples/weather_pipeline/) | 5 | Fetch weather, extract data, export |

## Documentation

| Document | Description |
|----------|-------------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Backend architecture |
| [docs/SCLPLL_LANGUAGE.md](docs/SCLPLL_LANGUAGE.md) | Language reference |
| [docs/PLUGIN_SYSTEM.md](docs/PLUGIN_SYSTEM.md) | Plugin development |
| [docs/WORKFLOW_ENGINE.md](docs/WORKFLOW_ENGINE.md) | Workflow engine |
| [docs/TEST_PLAN.md](docs/TEST_PLAN.md) | Test plan |
| [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md) | Test results |

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test suite
pytest tests/test_textual_tui.py -v
pytest tests/test_tui_features.py -v
pytest tests/test_tui_comprehensive.py -v
pytest tests/test_tui_advanced.py -v
pytest tests/test_tui_error_handling.py -v
```

**392 tests** covering:
- Unit tests (202)
- Textual UI tests (26)
- Feature tests (56)
- Comprehensive tests (49)
- Advanced tests (39)
- Error handling tests (20)

## Architecture

```
app/
  core/            Engine, models, contracts
  services/        Business logic
  storage/         SQLite database
  ui/              Textual TUI
    screens/       Request, Collections, History, etc.
    widgets/       Sidebar, Command Palette, JSON Viewer
    adapter.py     UI abstraction layer
functions/         Python extension functions
plugins/           Plugin packages
examples/          Example workflows
```

## License

MIT
