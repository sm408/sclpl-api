"""
@name: request_builder
@type: utility
@version: 1
@description: Build complex HTTP requests from components with template variable support

Config via workflow_variables: builder_method, builder_url, builder_headers (JSON),
builder_body, builder_query_params (JSON), builder_auth_type, builder_auth_config (JSON).
"""

import json


def run(ctx):
    method = ctx.workflow_variables.get("builder_method", "GET").upper()
    url = ctx.workflow_variables.get("builder_url", "")
    headers_raw = ctx.workflow_variables.get("builder_headers", "{}")
    body = ctx.workflow_variables.get("builder_body", "")
    params_raw = ctx.workflow_variables.get("builder_query_params", "{}")
    auth_type = ctx.workflow_variables.get("builder_auth_type", "")
    auth_config_raw = ctx.workflow_variables.get("builder_auth_config", "{}")

    if not url:
        return {"success": False, "error": "No URL specified"}

    try:
        headers = json.loads(headers_raw)
    except (json.JSONDecodeError, TypeError):
        headers = {}

    try:
        params = json.loads(params_raw)
    except (json.JSONDecodeError, TypeError):
        params = {}

    try:
        auth_config = json.loads(auth_config_raw)
    except (json.JSONDecodeError, TypeError):
        auth_config = {}

    if params:
        query_parts = [f"{k}={v}" for k, v in params.items()]
        separator = "&" if "?" in url else "?"
        url = url + separator + "&".join(query_parts)

    if auth_type == "bearer" and auth_config.get("token"):
        headers["Authorization"] = f"Bearer {auth_config['token']}"
    elif auth_type == "basic" and auth_config.get("username"):
        import base64
        creds = base64.b64encode(f"{auth_config['username']}:{auth_config.get('password', '')}".encode()).decode()
        headers["Authorization"] = f"Basic {creds}"
    elif auth_type == "api_key" and auth_config.get("key"):
        header_name = auth_config.get("header_name", "X-API-Key")
        headers[header_name] = auth_config["key"]

    request_spec = {
        "method": method,
        "url": url,
        "headers": headers,
        "body": body or None,
        "auth_type": auth_type,
    }

    ctx.workflow_variables["built_request"] = json.dumps(request_spec)

    return {
        "success": True,
        "request": request_spec,
    }
