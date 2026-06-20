# SCLPLAPI - Master Goal

## Product Vision

SCLPLAPI is a programmable, local-first API workflow studio with Python-native extensibility. It provides:

- **API Client** - Send HTTP requests with variable resolution
- **Workflow Runner** - Chain steps with dependencies and parallelism
- **Transformation Engine** - Process responses with Python functions
- **Export Workbench** - Output results to JSON, CSV, or reports

## Architecture

```
TUI (Rich/Prompt Toolkit)  →  Core Engine  →  Storage (SQLite)
        ↓                        ↓                  ↓
   CLI Interface           Workflow Engine      Collections
   Interactive Mode        Function Runner      History
                           Plugin Registry      Environments
                           Export Pipeline      Functions
```

## Technology Stack

| Layer | Technology |
|-------|-----------|
| TUI | Python, Rich, Prompt Toolkit |
| Core | Python, Pydantic, httpx |
| Storage | SQLite |
| Workflows | SCLPLL (custom DSL) |
| Plugins | Python modules with plugin.json manifests |

## Open Source First Philosophy

Before implementing any major subsystem, determine whether an actively maintained, permissively licensed open-source project already solves 80% of the problem.

Do NOT rebuild mature infrastructure from scratch. Instead:
1. Evaluate existing projects
2. Prefer adopting or forking proven foundations
3. Keep local modifications isolated
4. Preserve upstream compatibility
5. Document every deviation
6. Build product-specific functionality on top

## Development Philosophy

- Never build infrastructure that already exists in mature open-source projects
- Spend engineering effort only on what differentiates this product
- Every new feature should improve the platform, not just solve today's requirement
- Think in decades, not sprints
- Prefer extending existing abstractions over introducing new one-off systems

## Backend Rules

- Python owns all execution
- SQLite for storage, Pydantic for validation
- TUI is the primary interface
- No web frontend dependencies required
