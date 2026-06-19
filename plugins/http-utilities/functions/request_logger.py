"""
@name: request_logger
@type: http
@version: 1
@description: Log HTTP request and response details for debugging and auditing

Config via workflow_variables: log_level (debug/info), log_body (true/false).
"""

import json
import logging
import time

logger = logging.getLogger("sclplapi.request_logger")


def run(ctx):
    log_level = ctx.workflow_variables.get("log_level", "info").lower()
    log_body = ctx.workflow_variables.get("log_body", "true").lower() == "true"

    entry = {
        "timestamp": time.time(),
        "request": None,
        "response": None,
    }

    request = ctx.request
    if request:
        req_info = {
            "method": str(getattr(request, "method", "GET")),
            "url": getattr(request, "url", ""),
            "headers": {h.key: h.value for h in getattr(request, "headers", [])},
        }
        if log_body and getattr(request, "body", None):
            req_info["body"] = request.body
        entry["request"] = req_info

    response = ctx.metadata.get("response")
    if response:
        resp_info = {
            "status_code": getattr(response, "status_code", 0),
            "duration_ms": getattr(response, "duration_ms", 0),
        }
        if log_body:
            body = getattr(response, "body", None)
            if body:
                try:
                    resp_info["body"] = json.loads(body) if isinstance(body, str) else body
                except (json.JSONDecodeError, TypeError):
                    resp_info["body"] = str(body)[:1000]
        entry["response"] = resp_info

    log_fn = logger.debug if log_level == "debug" else logger.info
    log_fn("Request log: %s", json.dumps(entry, default=str, indent=2))

    ctx.metadata["request_log"] = entry
    return {"success": True, "logged": True, "entry": entry}
