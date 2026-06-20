# Plugin System

## Plugin Structure

```
plugins/my-plugin/
  plugin.json          # Plugin manifest
  functions/           # Python function modules
    my_function.py
  hooks/               # Pre/post request hooks (optional)
    pre_request.py
    post_response.py
```

## Plugin Manifest

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "What this plugin does",
  "functions": [
    {
      "name": "My Function",
      "description": "What the function does",
      "module": "functions.my_function",
      "entry_point": "run"
    }
  ]
}
```

## Writing Functions

```python
def run(context):
    """Execute the function.

    Args:
        context: ExecutionContext with step outputs, variables, etc.

    Returns:
        dict: Function output
    """
    user_data = context.get_step_output("fetch_users")
    return {"processed": True, "count": len(user_data)}
```

## Enabling Plugins

```bash
python -m app --enable-plugins
```
