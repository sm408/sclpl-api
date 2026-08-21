# Architecture

## Layer Direction

```
TUI (Textual) → UI Adapter → Services → Core → Storage
```

Each layer only depends on layers below it. No circular dependencies.

## Core (`app/core/`)

### Contracts (`app/core/contracts/`)
Abstract interfaces that define the system's boundaries:

- `RequestExecutor` — HTTP request execution
- `FunctionRunner` — Python function execution
- `EventBus` — Event pub/sub
- `PluginRegistry` — Plugin discovery and loading
- `VariableResolver` — Variable resolution
- `ExportPipeline` — Data export

### Engine (`app/core/engine/`)
Concrete implementations:

- `workflow.py` — Sequential workflow engine
- `parallel_workflow.py` — Parallel execution with dependency graph
- `sclpll_compiler.py` — SCLPLL script compiler/decompiler
- `sclpll_cli.py` — SCLPLL command-line runner
- `function_runner.py` — Python function execution
- `auth.py` — Authentication (Bearer, Basic, API Key)
- `event_bus.py` — Event pub/sub implementation
- `plugin_registry.py` — Plugin discovery and loading
- `variable_resolver.py` — Variable resolution with `{{var}}` syntax
- `hooks.py` — Pre/post request hooks

### Models (`app/core/models/`)
Data classes:

- `request.py` — RequestDef, HttpMethod, RequestParam
- `workflow.py` — WorkflowDef, WorkflowStep, StepType, RetryConfig
- `context.py` — ExecutionContext
- `collection.py` — Collection, CollectionItem
- `environment.py` — Environment, Variable
- `history.py` — HistoryEntry, RunStatus
- `monitor.py` — Monitor, MonitorEvent, MonitorStatus
- `export.py` — ExportResult, ExportFormat
- `plugin.py` — PluginManifest, PluginInfo

## Services (`app/services/`)

Business logic layer:

- `request_executor.py` — HTTP execution via httpx
- `collection_service.py` — Collection and request CRUD
- `environment_service.py` — Environment management
- `history_service.py` — Request history tracking
- `monitor_service.py` — Monitor CRUD
- `monitor_runner.py` — Background API polling with condition evaluation
- `export_service.py` — JSON/CSV/Excel export
- `full_export_service.py` — Full workspace backup
- `full_import_service.py` — Full workspace restore
- `batch_runner.py` — Batch request execution

## Storage (`app/storage/`)

SQLite persistence:

- `db.py` — Database connection and query helpers
- `migrations/` — Schema migrations
  - `m001_add_plugin_tables.py`
  - `m002_add_workflow_versioning.py`
  - `m003_add_export_presets.py`
  - `m004_add_monitors.py`

## UI (`app/ui/`)

Textual-based terminal interface:

- `textual_app.py` — Main Textual application with all screen wiring
- `adapter.py` — Abstract UIAdapter base class for future GUI
- `commands.py` — Command registry for command palette
- `screens/` — Individual screens
  - `request_editor.py` — URL, method, headers, body, auth
  - `response_viewer.py` — JSON tree, raw, headers, size
  - `collections.py` — Collection list with CRUD
  - `history.py` — History with filter and cleanup
  - `workflows.py` — Workflow list and execution
  - `environments.py` — Environment manager
  - `functions.py` — Function browser
  - `plugins.py` — Plugin browser
  - `monitors.py` — Live API monitor list and detail
  - `batch.py` — Batch execution with CSV import
  - `import_export.py` — Full/selective backup
  - `diff_viewer.py` — Response comparison
  - `log_viewer.py` — Log viewer with filtering
  - `settings.py` — Configuration editor
- `widgets/` — Reusable widgets
  - `sidebar.py` — Collection/workflow/env tree
  - `command_palette.py` — Ctrl+P command palette
  - `json_viewer.py` — Collapsible JSON tree
  - `method_badge.py` — Colored method badges

## Event Flow

```
User Action → Screen → Service → Engine → Event Bus → UI Update
                                                    → Log Entry
                                                    → Notification
```

Events published:
- `workflow.started`, `workflow.step_started`, `workflow.step_completed`, `workflow.step_failed`, `workflow.completed`
- `monitor.started`, `monitor.stopped`, `monitor.triggered`, `monitor.error`
- `request.started`, `response.received`
- `export.finished`
- `plugin.loaded`, `plugin.failed`
