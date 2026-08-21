"""
@name: retry_request
@type: http
@version: 1
@description: Retry failed HTTP requests with configurable backoff strategies

Supports fixed, exponential, and linear backoff. Reads retry config
from workflow_variables: retry_max_retries, retry_delay_ms, retry_strategy.
"""

import time


def run(ctx):
    request = ctx.request
    if not request:
        return {"success": False, "error": "No request in context"}

    max_retries = int(ctx.workflow_variables.get("retry_max_retries", "3"))
    delay_ms = int(ctx.workflow_variables.get("retry_delay_ms", "1000"))
    strategy = ctx.workflow_variables.get("retry_strategy", "fixed")
    retry_on_status = ctx.workflow_variables.get("retry_on_status", "500,502,503,504")

    retry_codes = {int(s.strip()) for s in retry_on_status.split(",") if s.strip()}

    response = ctx.metadata.get("response")
    if not response:
        return {"success": False, "error": "No response in context"}

    status_code = getattr(response, "status_code", 0)
    if status_code not in retry_codes:
        return {
            "success": True,
            "retry_needed": False,
            "status_code": status_code,
            "message": "Response status does not require retry",
        }

    attempts = 0
    last_status = status_code

    for attempt in range(max_retries):
        if strategy == "exponential":
            sleep_s = (delay_ms / 1000) * (2 ** attempt)
        elif strategy == "linear":
            sleep_s = (delay_ms / 1000) * (attempt + 1)
        else:
            sleep_s = delay_ms / 1000

        time.sleep(sleep_s)
        attempts += 1

        new_response = ctx.metadata.get("response")
        if new_response:
            last_status = getattr(new_response, "status_code", 0)
            if last_status not in retry_codes:
                return {
                    "success": True,
                    "retry_needed": True,
                    "attempts": attempts,
                    "final_status": last_status,
                    "message": f"Succeeded after {attempts} retries",
                }

    return {
        "success": False,
        "retry_needed": True,
        "attempts": attempts,
        "final_status": last_status,
        "message": f"Failed after {attempts} retries",
    }
