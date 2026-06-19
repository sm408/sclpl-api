# SCLPLAPI Developer Guide

This guide is for developers contributing to SCLPLAPI. It covers architecture, code conventions, extension points, and how to add new features.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Layer Rules](#layer-rules)
3. [Repository Structure](#repository-structure)
4. [Adding New Features](#adding-new-features)
5. [Extending the Workflow Engine](#extending-the-workflow-engine)
6. [Adding New Step Types](#adding-new-step-types)
7. [The Function System](#the-function-system)
8. [The Event Bus](#the-event-bus)
9. [Storage and Migrations](#storage-and-migrations)
10. [Writing Tests](#writing-tests)
11. [Code Conventions](#code-conventions)
12. [Anti-Patterns to Avoid](#anti-patterns-to-avoid)

---

## Architecture Overview

SCLPLAPI follows a strict 4-layer architecture:

```
┌─────────────────────────────┐
│           UI Layer          │  Rendering, interaction, progress display
├─────────────────────────────┤
│        Services Layer       │  Use-case orchestration, lifecycle management
├─────────────────────────────┤
│          Core Layer         │  Execution models, graph logic, variable resolution
├─────────────────────────────┤
│   Storage / Infrastructure  │  SQLite, file I/O, HTTP transport, discovery
└─────────────────────────────┘
```

**Direction**: `UI -> Services -> Core -> Storage`

Dependencies flow downward only. No layer may reach upward or sideways into a sibling.

### UI Layer

**Owns**: rendering, interaction, progress display, workspace navigation

**Must not own**: HTTP execution, workflow engine logic, persistence rules

### Services Layer

**Owns**: use-case orchestration, request submission coordination, workflow lifecycle orchestration, event publication for side effects

This is the glue layer. It coordinates between UI and Core without leaking implementation details in either direction.

### Core Layer

**Owns**: request execution models, workflow graph logic, variable resolution, function context contracts, export pipeline contracts

**Critical rule**: Core must remain UI-independent. It should be runnable headless, testable in isolation, and free of any rendering concerns.

### Storage / Infrastructure Layer

**Owns**: SQLite access, schema migrations, import/export file I/O, HTTP transport adapters, plugin and function discovery I/O

---

## Layer Rules

These rules are non-negotiable:

| Rule | Description |
|------|-------------|
| **Downward only** | Dependencies flow UI -> Services -> Core -> Storage |
| **No upward imports** | Core must never import from Services or UI |
| **No sibling imports** | Services A must not import from Services B directly — go through Core |
| **Core is headless** | Core must be testable and runnable without any UI |
| **Contracts are stable** | Function and plugin contracts are user-facing APIs |
| **No hidden globals** | Use typed, explicit execution context objects |
| **Event bus is in-process** | Lightweight, no external message brokers |

### What Belongs Where

| Concern | Layer | Example |
|---------|-------|---------|
| HTTP request execution | Core | `RequestExecutor.run()` |
| Workflow graph traversal | Core | `WorkflowEngine.execute()` |
| Variable resolution | Core | `VariableResolver.resolve()` |
| Request submission from UI | Services | `RequestService.submit()` |
| Workflow lifecycle | Services | `WorkflowService.start()` |
| Rendering response viewer | UI | `ResponseViewer.render()` |
| SQLite queries | Storage | `WorkflowRepository.save()` |
| Function file discovery | Storage | `FunctionDiscovery.scan()` |

---

## Repository Structure

```
sclpl-api/
  app/
    core/              # Core layer: execution models, engines, contracts
      engine/          # Workflow engine, request executor, SCLPLL compiler
      models/          # Dataclasses for internal models
      contracts/       # Interface definitions
    services/          # Services layer: orchestration, lifecycle
    storage/           # Storage layer: SQLite, migrations, file I/O
    ui/                # UI layer: rendering, interaction
  functions/           # User-authored Python functions (discovered at runtime)
    transformers/
    exporters/
    auth/
  data/                # Runtime data: SQLite database, cache
  docs/                # Documentation
  examples/            # Working pipeline examples
  tests/               # Test suite
  requirements/        # Implementation requirement sets
  rules/               # MiMo instruction files
  pyproject.toml       # Project config
```

---

## Adding New Features

### Step 1: Identify the Layer

Ask: "Does this touch rendering?" If no, it's not UI. Ask: "Is this orchestration or business logic?" If orchestration, it's Services. If core execution logic, it's Core.

### Step 2: Define the Contract

Before writing implementation, define the contract (interface or dataclass) in `app/core/contracts/`:

```python
# app/core/contracts/step_executor.py
from abc import ABC, abstractmethod
from app.core.models.context import ExecutionContext

class StepExecutor(ABC):
    @abstractmethod
    async def execute(self, step: StepDefinition, ctx: ExecutionContext) -> StepResult:
        ...
```

### Step 3: Implement in the Correct Layer

- Core logic goes in `app/core/`
- Service orchestration goes in `app/services/`
- Storage operations go in `app/storage/`
- UI rendering goes in `app/ui/`

### Step 4: Write Tests

Tests go in `tests/` mirroring the source structure:

```
tests/
  core/
    test_variable_resolver.py
    test_workflow_engine.py
  services/
    test_workflow_service.py
  storage/
    test_workflow_repository.py
```

### Step 5: Update Documentation

If the feature changes architecture or public contracts, update the relevant `.md` file in the root or `docs/`.

---

## Extending the Workflow Engine

The workflow engine is a graph execution runtime. It processes nodes (steps) and edges (dependencies).

### Execution Model

```python
# Simplified execution flow
async def execute_workflow(workflow: WorkflowDefinition, ctx: ExecutionContext):
    graph = build_dependency_graph(workflow.steps)

    while graph.has_pending():
        # Find all steps whose dependencies are satisfied
        ready = graph.get_ready_steps()

        # Execute ready steps in parallel
        results = await asyncio.gather(*[
            execute_step(step, ctx) for step in ready
        ])

        # Update context with results
        for step, result in zip(ready, results):
            ctx.set_step_output(step.id, result)
            graph.mark_complete(step.id)

    return ctx
```

### Key Extension Points

| Extension | Where | How |
|-----------|-------|-----|
| New step type | `app/core/engine/` | Implement `StepExecutor` interface |
| New variable source | `app/core/` | Extend `VariableResolver` |
| New export format | `app/core/` | Implement `Exporter` contract |
| Retry strategy | `app/core/engine/` | Add to retry configuration |
| Conditional execution | `app/core/engine/` | Add condition evaluator |

### Variable Resolution

The resolver checks scopes in priority order:

```python
# Variable precedence (highest to lowest)
PRECEDENCE = [
    "step",          # Step-level override
    "runtime",       # Set by function during execution
    "batch_row",     # Current CSV row
    "workflow",      # Workflow-level @var definition
    "environment",   # Selected environment
    "global",        # Global defaults
]
```

---

## Adding New Step Types

### 1. Define the Step Type Enum

```python
# app/core/models/step.py
from enum import Enum

class StepType(str, Enum):
    REQUEST = "request"
    FUNCTION = "function"
    EXPORT = "export"
    TRANSFORMER = "transformer"
    # Add your new type:
    DELAY = "delay"
```

### 2. Create the Executor

```python
# app/core/engine/delay_executor.py
import asyncio
from app.core.contracts.step_executor import StepExecutor
from app.core.models.context import ExecutionContext

class DelayExecutor(StepExecutor):
    async def execute(self, step, ctx: ExecutionContext):
        seconds = step.config.get("seconds", 1)
        await asyncio.sleep(seconds)
        return StepResult(status="completed", output={"waited": seconds})
```

### 3. Register in the Engine

```python
# app/core/engine/registry.py
EXECUTORS = {
    StepType.REQUEST: RequestExecutor(),
    StepType.FUNCTION: FunctionExecutor(),
    StepType.EXPORT: ExportExecutor(),
    StepType.DELAY: DelayExecutor(),  # Register here
}
```

### 4. Add SCLPLL Support (Optional)

If the new step type should be expressible in SCLPLL:

```sclpll
@step wait_a_bit -> delay_result
    delay 5
```

Update the SCLPLL compiler to recognize the `delay` keyword and map it to the `DELAY` step type.

### 5. Write Tests

```python
# tests/core/engine/test_delay_executor.py
import pytest
from app.core.engine.delay_executor import DelayExecutor

@pytest.mark.asyncio
async def test_delay_executor():
    executor = DelayExecutor()
    step = MockStep(config={"seconds": 0.1})
    ctx = ExecutionContext()
    result = await executor.execute(step, ctx)
    assert result.status == "completed"
    assert result.output["waited"] == 0.1
```

---

## The Function System

Functions are the primary extensibility mechanism. They are Python files discovered from the filesystem.

### Discovery Flow

```
functions/
  transformers/
    extract_date.py     <- discovered
    merge_data.py       <- discovered
  exporters/
    export_csv.py       <- discovered
```

Discovery scans recursively, reads docstring headers, and registers functions by `@name`.

### Function Contract

```python
"""
@name: My Function
@type: post_response
@version: 1
"""

def run(ctx):
    # Access response
    data = ctx.response.json()

    # Set variables for downstream steps
    ctx.workflow_variables["extracted"] = data["field"]

    # Always return ctx
    return ctx
```

### Adding a New Function Type

1. Define the type in `app/core/models/function.py`
2. Add the execution hook in the engine (pre-request, post-response, etc.)
3. Document the contract in `FUNCTION_SYSTEM.md`

---

## The Event Bus

The event bus is lightweight and in-process. It enables decoupled communication between subsystems.

### Usage

```python
from app.core.events import EventBus

bus = EventBus()

# Subscribe
bus.on("workflow.completed", handle_completion)

# Publish
bus.emit("workflow.completed", {"workflow_id": "my-pipeline", "status": "success"})
```

### Rules

- No external brokers (no Redis, no RabbitMQ)
- Synchronous dispatch by default
- Async dispatch for I/O-bound handlers
- Keep event payloads typed and small

---

## Storage and Migrations

### SQLite First

SQLite is the default persistence backend. All schema changes must be versioned.

### Adding a Migration

```python
# app/storage/migrations/003_add_workflow_tags.py
from app.storage.migrations.base import Migration

class AddWorkflowTags(Migration):
    version = 3
    description = "Add tags column to workflows"

    def up(self, conn):
        conn.execute("ALTER TABLE workflows ADD COLUMN tags TEXT DEFAULT ''")

    def down(self, conn):
        conn.execute("ALTER TABLE workflows DROP COLUMN tags")
```

### Migration Rules

- Every schema change gets a numbered migration
- User data must be migratable — never silently invalidate saved workspaces
- Test both `up` and `down` paths

---

## Writing Tests

### Test Priorities

| Priority | Area | Coverage Target |
|----------|------|-----------------|
| 1 | Variable resolution | Very high |
| 2 | Workflow execution | Very high |
| 3 | Function execution contracts | High |
| 4 | Plugin loading | High |
| 5 | Exporters/transformations | High |
| 6 | Migrations | High |
| 7 | Retry/timeout behavior | Medium |
| 8 | UI | Minimal sanity |

### Test Philosophy

- Test determinism over UI cosmetics
- Test behavior at boundaries
- Isolate async and cancellation behavior
- Prefer focused subsystem tests over fake end-to-end theater

### Example Test

```python
# tests/core/test_variable_resolver.py
import pytest
from app.core.models.context import ExecutionContext
from app.core.variable_resolver import VariableResolver

def test_step_precedence_over_workflow():
    ctx = ExecutionContext()
    ctx.set_workflow_variable("city", "London")
    ctx.set_step_variable("city", "Paris")

    resolver = VariableResolver(ctx)
    assert resolver.resolve("{{city}}") == "Paris"

def test_missing_variable_raises():
    ctx = ExecutionContext()
    resolver = VariableResolver(ctx)

    with pytest.raises(VariableNotFoundError):
        resolver.resolve("{{nonexistent}}")
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific module
pytest tests/core/

# Run only async tests
pytest -m asyncio
```

---

## Code Conventions

### Formatting

- **Ruff** for linting and formatting
- **Black**-compatible formatting
- Line length: 88 characters (Black default)

### Type Annotations

- Typed core contracts are mandatory
- Use `dataclasses` for internal execution/runtime models
- Use `Pydantic` for external or untrusted data boundaries

```python
# Internal model — dataclass
from dataclasses import dataclass

@dataclass
class StepResult:
    status: str
    output: dict
    error: str | None = None

# External boundary — Pydantic
from pydantic import BaseModel

class WorkflowCreateRequest(BaseModel):
    name: str
    description: str = ""
    steps: list[dict]
```

### Async Discipline

- No blocking network calls in async flows
- Background tasks must be cancellable
- Request and workflow execution paths need timeout support

```python
# Good: async with timeout
async def execute_request(url: str, timeout: float = 30.0):
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=timeout)
        return response

# Bad: blocking call in async context
async def execute_request_bad(url: str):
    response = requests.get(url)  # BLOCKS the event loop!
    return response
```

### File Size

- Soft limit: 500-700 LOC
- Treat 1000+ LOC files as architectural warnings
- Split large files by responsibility

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | What to Do Instead |
|-------------|-------------|-------------------|
| God files | Hard to test, hard to navigate | Split by responsibility |
| Circular imports | Runtime errors, fragile code | Respect layer direction |
| Hidden globals | Untestable, unpredictable | Use explicit context objects |
| UI-driven business logic | Couples rendering to logic | Keep logic in Core/Services |
| Duplicated variable resolution | Bugs multiply | Use the single `VariableResolver` |
| Plugin reliance on internals | Breaks on refactor | Use documented extension points |
| Blocking in async | Kills concurrency | Use async HTTP clients |
| Untyped contracts | Runtime surprises | Use dataclasses/Pydantic |

---

## Quick Reference: Where Does This Go?

| I want to... | Go to... |
|-------------|----------|
| Add a new API endpoint | `app/services/` (orchestration) + `app/core/` (logic) |
| Add a new step type | `app/core/engine/` + executor class |
| Add a new export format | `app/core/` (exporter contract) |
| Add a CLI command | `app/ui/cli/` |
| Add a database table | `app/storage/migrations/` |
| Add a function type | `app/core/models/function.py` |
| Add an event handler | `app/core/events/` |
| Fix a bug in workflow execution | `app/core/engine/` |
| Add a test | `tests/` mirroring source structure |

---

## Next Steps

- **Architecture Deep Dive**: [ARCHITECTURE.md](../../../ARCHITECTURE.md)
- **Workflow Engine Design**: [WORKFLOW_ENGINE.md](../../../WORKFLOW_ENGINE.md)
- **Coding Standards**: [CODING_STANDARDS.md](../../../CODING_STANDARDS.md)
- **Testing Strategy**: [TESTING_STRATEGY.md](../../../TESTING_STRATEGY.md)
- **Function System**: [FUNCTION_SYSTEM.md](../../../FUNCTION_SYSTEM.md)
- **Plugin SDK**: [PLUGIN_SDK.md](../../../PLUGIN_SDK.md)
- **User Guide**: [User Perspective](../user/README.md)
