# SCLPLAPI - Master Goal

## Product Vision

SCLPLAPI is a programmable, local-first API workflow studio with Python-native extensibility. It provides:

- **API Client** — Send HTTP requests with variable resolution
- **Workflow Runner** — Chain steps with dependencies and parallelism
- **Transformation Engine** — Process responses with Python functions
- **Live Monitor** — Watch APIs in background, get notified on events
- **Export Workbench** — Output results to JSON, CSV, or reports

## Architecture

```
Textual TUI  →  UI Adapter  →  Service Layer  →  Core Engine  →  Storage (SQLite)
    ↓              ↓               ↓                ↓                ↓
  Screens       Abstract        Collections      Workflow         SQLite
  Widgets       Interface       Environments     SCLPLL           Migrations
  Commands      (future GUI)    History          Functions
                                Monitors         Plugins
                                Export           Event Bus
```

## Technology Stack

| Layer | Technology |
|-------|-----------|
| TUI | Python, Textual, Rich |
| Core | Python, Pydantic, httpx |
| Storage | SQLite, aiosqlite |
| Workflows | SCLPLL (custom DSL) |
| Plugins | Python modules with plugin.json manifests |
| Monitors | Background polling with condition evaluation |

## Key Components

### TUI (`app/ui/`)
- `textual_app.py` — Main Textual application
- `adapter.py` — Abstract UIAdapter base class
- `screens/` — Request, Collections, History, Workflows, Environments, Functions, Plugins, Monitors, Batch, Import/Export, Diff, Logs, Settings
- `widgets/` — Sidebar, Command Palette, JSON Viewer, Method Badge
- `commands.py` — Command registry for palette

### Services (`app/services/`)
- `collection_service.py` — Collection and request CRUD
- `environment_service.py` — Environment management
- `history_service.py` — Request history
- `monitor_service.py` — Monitor CRUD
- `monitor_runner.py` — Background API polling
- `export_service.py` — JSON/CSV/Excel export
- `full_export_service.py` — Full workspace backup
- `full_import_service.py` — Full workspace restore
- `request_executor.py` — HTTP execution
- `batch_runner.py` — Batch request execution

### Core (`app/core/`)
- `engine/` — Workflow, SCLPLL compiler, parallel execution, plugins, event bus
- `models/` — Request, Workflow, Context, Collection, Environment, History, Monitor, Plugin, Export
- `contracts/` — Abstract interfaces

### Storage (`app/storage/`)
- `db.py` — SQLite connection
- `migrations/` — Schema migrations (4 total)

## Development Philosophy

- Python owns all execution
- TUI is the primary interface
- No web frontend dependencies required
- Services are UI-agnostic (CLI, TUI, future GUI all use same services)
- Event-driven architecture for real-time updates

## Backend Rules

- SQLite for storage, Pydantic for validation
- All async operations through service layer
- Event bus for cross-component communication
- Background tasks for monitors and batch execution
