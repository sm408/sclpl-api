# Workflow Engine

## Execution Model

### Sequential Steps

Steps without dependencies run in order:

```sclpll
@step first -> data1
    request GET {{base_url}}/step1

@step second <- first -> data2
    request GET {{base_url}}/step2/{{data1.body.id}}
```

### Parallel Steps

Steps with no dependencies on each other run in parallel:

```sclpll
@step users -> user_data
    request GET {{base_url}}/users

@step posts -> post_data
    request GET {{base_url}}/posts

@step merge <- users, posts -> combined
    func Merge Data
```

## Context

Each step receives an `ExecutionContext`:

```python
class ExecutionContext:
    variables: dict          # Workflow variables
    step_outputs: dict       # Previous step outputs
    environment: dict        # Active environment variables
    request: RequestDef      # Current request (for request steps)
```

## Error Handling

### Retries

```sclpll
@step flaky_api -> data
    request GET {{base_url}}/unreliable
    retry 3 exponential 1000
```

## Implementation

- `app/core/engine/workflow.py` — Sequential engine
- `app/core/engine/parallel_workflow.py` — Parallel engine with dependency graph
- `app/core/engine/sclpll_compiler.py` — SCLPLL to JSON compilation
