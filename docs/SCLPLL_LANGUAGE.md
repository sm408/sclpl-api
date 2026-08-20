# SCLPLL Language Reference

SCLPLL (SCLPL Language) is a domain-specific scripting language for defining API workflows.

## Workflow Definition

```sclpll
@workflow my-workflow "My Workflow Name"
    Description of what this workflow does.
```

## Variables

```sclpll
@base_url https://api.example.com
@var api_key = abc123
```

Variables are referenced with `{{variable_name}}` syntax.

## Steps

### HTTP Request

```sclpll
@step fetch_users -> users_data
    request GET {{base_url}}/users
```

With headers:

```sclpll
@step fetch_users -> users_data
    request GET {{base_url}}/users
    header Authorization Bearer {{api_key}}
```

With body:

```sclpll
@step create_user -> new_user
    request POST {{base_url}}/users
    body {"name": "John", "email": "john@example.com"}
```

### Python Function

```sclpll
@step process_data <- fetch_users -> processed
    func Process User Data
```

### Dependencies

```sclpll
@step analyze <- fetch_users, fetch_posts -> analysis
    func Analyze Data
```

Steps without dependencies run in parallel.

## Control Flow

### Conditions

```sclpll
@step check_status <- fetch_users
    when {{users_data.status_code}} == 200
    func Process Users
```

### Loops

```sclpll
@step fetch_each <- user_list
    foreach {{user_list}} as user
    request GET {{base_url}}/users/{{user.id}}
```

## Error Handling

### Retry

```sclpll
@step unreliable_api -> data
    request GET {{base_url}}/flaky
    retry 3 exponential 1000
```

Retry strategies: `fixed`, `exponential`, `linear`

### Timeout

```sclpll
@step slow_api -> data
    request GET {{base_url}}/slow
    timeout 30000
```

## Compilation

```bash
python -m app.core.engine.sclpll_cli compile script.sclpll
python -m app.core.engine.sclpll_cli run script.sclpll
python -m app.core.engine.sclpll_cli decompile workflow.json
```
