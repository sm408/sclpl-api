"""
@name: auth_handler
@type: utility
@version: 1
@description: Handle authentication flows: token refresh, OAuth2 client credentials, API key rotation

Config via workflow_variables: auth_flow (token_refresh/client_credentials/api_key_rotate),
auth_token_url, auth_client_id, auth_client_secret, auth_scope,
auth_api_key, auth_api_key_header.
"""

import json
import time
import urllib.request
import urllib.parse


def _client_credentials(token_url, client_id, client_secret, scope):
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": scope,
    }).encode()

    req = urllib.request.Request(token_url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            return {
                "access_token": body.get("access_token"),
                "expires_in": body.get("expires_in"),
                "token_type": body.get("token_type"),
            }
    except Exception as exc:
        return {"error": str(exc)}


def run(ctx):
    flow = ctx.workflow_variables.get("auth_flow", "token_refresh")

    if flow == "client_credentials":
        token_url = ctx.workflow_variables.get("auth_token_url", "")
        client_id = ctx.workflow_variables.get("auth_client_id", "")
        client_secret = ctx.workflow_variables.get("auth_client_secret", "")
        scope = ctx.workflow_variables.get("auth_scope", "")

        if not all([token_url, client_id, client_secret]):
            return {"success": False, "error": "Missing auth_token_url, auth_client_id, or auth_client_secret"}

        result = _client_credentials(token_url, client_id, client_secret, scope)
        if "error" in result:
            return {"success": False, "error": result["error"]}

        ctx.workflow_variables["access_token"] = result["access_token"]
        return {
            "success": True,
            "flow": "client_credentials",
            "token_type": result.get("token_type"),
            "expires_in": result.get("expires_in"),
        }

    elif flow == "token_refresh":
        refresh_token = ctx.workflow_variables.get("auth_refresh_token", "")
        token_url = ctx.workflow_variables.get("auth_token_url", "")
        client_id = ctx.workflow_variables.get("auth_client_id", "")

        if not all([refresh_token, token_url]):
            return {"success": False, "error": "Missing auth_refresh_token or auth_token_url"}

        data = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }).encode()

        req = urllib.request.Request(token_url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode())
                ctx.workflow_variables["access_token"] = body.get("access_token", "")
                if body.get("refresh_token"):
                    ctx.workflow_variables["auth_refresh_token"] = body["refresh_token"]
                return {
                    "success": True,
                    "flow": "token_refresh",
                    "token_type": body.get("token_type"),
                    "expires_in": body.get("expires_in"),
                }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    elif flow == "api_key_rotate":
        current_key = ctx.workflow_variables.get("auth_api_key", "")
        new_key = ctx.workflow_variables.get("auth_new_api_key", "")
        if not new_key:
            return {"success": False, "error": "No auth_new_api_key provided"}
        ctx.workflow_variables["auth_api_key"] = new_key
        return {
            "success": True,
            "flow": "api_key_rotate",
            "previous_key_prefix": current_key[:8] + "..." if len(current_key) > 8 else current_key,
        }

    return {"success": False, "error": f"Unknown auth flow: {flow}"}
