# Documentation

This directory contains documentation for SCLPLAPI.

## Quick Links

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Backend architecture and layer design |
| [SCLPLL_LANGUAGE.md](SCLPLL_LANGUAGE.md) | SCLPLL scripting language reference |
| [PLUGIN_SYSTEM.md](PLUGIN_SYSTEM.md) | Plugin development guide |
| [WORKFLOW_ENGINE.md](WORKFLOW_ENGINE.md) | Workflow engine design |
| [TEST_PLAN.md](TEST_PLAN.md) | TUI test plan |
| [TEST_RESULTS.md](TEST_RESULTS.md) | Test execution results |

## Architecture

- **Core** (`app/core/`) — Engine, models, contracts
- **Services** (`app/services/`) — Business logic (collections, environments, history, monitors, export)
- **Storage** (`app/storage/`) — SQLite database with migrations
- **TUI** (`app/ui/`) — Textual-based terminal interface

## Key Concepts

### SCLPLL Language
Custom scripting language for defining API workflows with parallel execution, dependencies, and Python functions.

### Live Monitor
Background API polling with condition evaluation and notifications. Monitor endpoints while working on other tasks.

### Event Bus
In-process pub/sub system for real-time updates between components (workflow execution, monitors, UI).

### Plugin System
Filesystem-based plugin discovery with hooks, functions, and workflows.
