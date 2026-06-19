# Plugin System

SCLPLAPI's plugin system provides filesystem-based extensibility for functions, workflows, and request hooks.

## Quick Start

### Create a plugin

```bash
sclplapi plugins create my-plugin
```

This scaffolds:

```
plugins/my-plugin/
├── plugin.json          # Manifest
├── functions/
│   └── example.py       # Example function
├── workflows/           # Workflow definitions
├── hooks/               # Pre/post request hooks
└── README.md
```

### List plugins

```bash
sclplapi plugins list
```

### View plugin details

```bash
sclplapi plugins info my-plugin
```

### Reload plugins (hot-reload)

```bash
sclplapi plugins reload
```

## Plugin Manifest

Every plugin requires a `plugin.json` manifest:

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "What this plugin does",
  "author": "Your Name",
  "functions": ["functions/*.py"],
  "workflows": ["workflows/*.json"],
  "hooks": {
    "pre_request": "hooks/pre_request.py",
    "post_response": "hooks/post_response.py"
  },
  "variables": {
    "api_base_url": "https://api.example.com",
    "timeout": "30"
  },
  "dependencies": ["other-plugin"]
}
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique plugin identifier (kebab-case) |
| `version` | Yes | Semantic version string |
| `description` | No | Human-readable description |
| `author` | No | Plugin author name |
| `functions` | No | Glob patterns for function files |
| `workflows` | No | Glob patterns for workflow JSON files |
| `hooks` | No | Hook type to script path mapping |
| `variables` | No | Default variables merged into execution context |
| `dependencies` | No | Other plugin names this plugin depends on |

## Plugin Functions

Functions follow the same pattern as global functions — Python files with a `run(ctx)` entrypoint and metadata docstring:

```python
"""
@name: my_function
@type: utility
@description: Does something useful
"""

def run(ctx):
    # Access context
    variables = ctx.workflow_variables
    request = ctx.request

    # Return value becomes step output
    return {"result": "computed value"}
```

Plugin functions are discovered alongside global functions and appear in `sclplapi functions`.

### Function types

- `utility` — General-purpose helpers
- `transformer` — Data transformation
- `pre_request` — Runs before request execution
- `post_response` — Runs after response received

## Plugin Workflows

Workflows are JSON files in the plugin's `workflows/` directory. They use the same schema as standalone workflows:

```json
{
  "id": "my-workflow",
  "name": "My Plugin Workflow",
  "description": "Demonstrates plugin workflows",
  "steps": [
    {
      "id": "step1",
      "name": "Run Function",
      "type": "function",
      "function_name": "my_function",
      "output_variable": "result"
    }
  ],
  "variables": {
    "key": "value"
  }
}
```

## Plugin Hooks

Hooks are Python scripts that run at specific points in the request lifecycle.

### Pre-request hook

Runs before each HTTP request. Receives and returns `ExecutionContext`:

```python
"""
@name: add_headers
@type: pre_request
@description: Adds custom headers
"""

async def run(ctx):
    if ctx.request:
        from app.core.models.request import RequestParam
        ctx.request.headers.append(
            RequestParam(key="X-Custom", value="from-plugin")
        )
    return ctx
```

### Post-response hook

Runs after each HTTP response:

```python
"""
@name: log_response
@type: post_response
@description: Logs response details
"""

async def run(ctx):
    response = ctx.metadata.get("response")
    if response:
        ctx.metadata["processed_by_plugin"] = True
    return ctx
```

## Plugin Variables

Variables defined in `plugin.json` are merged into the execution context. They are available as `{{variable_name}}` templates in requests and workflows.

Plugin variables are merged after environment variables, so they can provide defaults that environments override.

## Plugin Dependencies

Plugins can declare dependencies on other plugins:

```json
{
  "dependencies": ["base-utils", "auth-helpers"]
}
```

Dependencies are loaded automatically before the dependent plugin. Circular dependencies raise an error.

## Integration with Global Systems

### Function Discovery

Plugin functions appear alongside global functions:

```bash
sclplapi functions --include-plugins
```

### Workflow Execution

Plugin workflows can be executed by referencing their JSON file path.

### Hook Execution

Plugin hooks are automatically registered with the `FunctionHookRunner` and execute alongside global hooks.

## Plugin Lifecycle

1. **Discover** — Scan `plugins/` directory for `plugin.json` manifests
2. **Load** — Parse manifest, resolve dependencies
3. **Activate** — Load functions, workflows, hooks; merge variables
4. **Deactivate** — Unload plugin resources
5. **Reload** — Re-scan and refresh all plugins (hot-reload)

## API Reference

### `FilesystemPluginRegistry`

```python
from app.core.engine.plugin_registry import FilesystemPluginRegistry

registry = FilesystemPluginRegistry("plugins")

# Discover all plugins (metadata only)
plugins = registry.discover()

# Fully load a plugin (functions, workflows, hooks)
info = registry.load("my-plugin")

# List all known plugins
all_plugins = registry.list_plugins()

# Get a specific plugin
info = registry.get_plugin("my-plugin")

# Unload a plugin
registry.unload("my-plugin")

# Hot-reload all plugins
registry.reload()

# Get all active plugin functions
functions = registry.get_all_functions()

# Get all active plugin variables
variables = registry.get_all_variables()

# Scaffold a new plugin
plugin_dir = registry.scaffold_plugin("new-plugin")
```

### `PluginManifest`

```python
from app.core.models.plugin import PluginManifest, PluginInfo, PluginStatus
```

## Architecture Rules

- Plugins operate through public contracts only
- Plugin errors are isolated and reported clearly
- Plugin loading must not require core changes
- Local-first discovery is the default
- Invalid plugins fail closed with clear diagnostics
