# Architecture

## Layer Direction

```
UI (TUI/CLI) → Services → Core → Storage
```

## Core (`app/core/`)

### Contracts (`app/core/contracts/`)
- `RequestExecutor` — HTTP request execution
- `FunctionRunner` — Python function execution
- `EventBus` — Event pub/sub
- `PluginRegistry` — Plugin discovery and loading
- `VariableResolver` — Variable resolution
- `ExportPipeline` — Data export

### Engine (`app/core/engine/`)
- `workflow.py` — Sequential workflow engine
- `parallel_workflow.py` — Parallel execution with dependency graph
- `sclpll_compiler.py` — SCLPLL script compiler/decompiler
- `sclpll_cli.py` — SCLPLL command-line runner
- `function_runner.py` — Python function execution
- `auth.py` — Authentication (Bearer, Basic, API Key)
- `event_bus.py` — Event pub/sub implementation
- `plugin_registry.py` — Plugin discovery and loading
- `variable_resolver.py` — Variable resolution with `{{var}}` syntax

### Models (`app/core/models/`)
- `request.py` — RequestDef, HttpMethod, RequestParam
- `workflow.py` — WorkflowDef, WorkflowStep, StepType, RetryConfig
- `context.py` — ExecutionContext
- `collection.py` — Collection, CollectionItem
- `environment.py` — Environment
- `history.py` — HistoryEntry
- `export.py` — ExportResult
- `plugin.py` — PluginManifest, PluginInfo

## Services (`app/services/`)
- `request_executor.py` — HTTP execution via httpx
- `collection_service.py` — Collection and request CRUD
- `environment_service.py` — Environment management
- `history_service.py` — Request history tracking
- `export_service.py` — JSON/CSV export
- `full_export_service.py` — Full workspace export
- `full_import_service.py` — Full workspace import
- `batch_runner.py` — Batch request execution

## Storage (`app/storage/`)
- `db.py` — Database connection and query helpers
- `migrations/` — Schema migrations

## UI (`app/ui/`)
- `tui.py` — Rich-based TUI with interactive menus
- `app.py` — Composition root
- `cli.py` — CLI subcommands
- `launcher.py` — Entry point and setup wizard
- `logo.py` — ASCII art branding
