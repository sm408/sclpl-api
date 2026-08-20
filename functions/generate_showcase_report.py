"""
@name: Generate Showcase Report
@type: transformer
@version: 1

Generates the final comprehensive report combining all analysis.
Demonstrates accessing multiple step outputs and workflow variables.
"""

import json
from datetime import datetime


def run(ctx):
    # Get analytics
    analytics_raw = ctx.workflow_variables.get("analytics", "{}")
    try:
        analytics = json.loads(analytics_raw) if isinstance(analytics_raw, str) else analytics_raw
    except (json.JSONDecodeError, TypeError):
        analytics = {}

    # Get conditional handler results
    success_status = ctx.workflow_variables.get("success_status", "N/A")
    success_message = ctx.workflow_variables.get("success_message", "")
    error_status = ctx.workflow_variables.get("error_status", "N/A")
    error_message = ctx.workflow_variables.get("error_message", "")

    # Get user info
    first_user_name = ctx.workflow_variables.get("first_user_name", "N/A")
    first_user_email = ctx.workflow_variables.get("first_user_email", "N/A")
    user_full_address = ctx.workflow_variables.get("user_full_address", "N/A")

    # Build comprehensive report
    report = {
        "report_metadata": {
            "generated_at": datetime.now().isoformat(),
            "pipeline": "SCLPLAPI Feature Showcase",
            "version": "1.0",
            "features_demonstrated": [
                "@workflow, @base_url, @var directives",
                "GET, POST, PUT, DELETE requests",
                "Headers and Body payloads",
                "Dependencies (<-) and Output variables (->)",
                "Dot notation ({{step.field.subfield}})",
                "@foreach loops (Process User List)",
                "@repeat loops (batch_fetch, rate_limited_fetch)",
                "@when conditions (success_handler, error_handler)",
                "@semaphore rate limiting (rate_limited_fetch)",
                "Function steps (8 custom functions)",
            ],
        },
        "executive_summary": analytics.get("summary", {}),
        "api_operations": {
            "GET_requests": 3,
            "POST_requests": 1,
            "PUT_requests": 1,
            "DELETE_requests": 1,
            "batch_operations": 8,
            "conditional_executions": 2,
        },
        "conditional_results": {
            "success_path": {
                "status": success_status,
                "message": success_message,
            },
            "error_path": {
                "status": error_status,
                "message": error_message,
            },
        },
        "user_insights": {
            "first_user": first_user_name,
            "email": first_user_email,
            "address": user_full_address,
        },
        "top_contributors": analytics.get("top_contributors", []),
        "city_distribution": analytics.get("city_distribution", {}),
        "company_distribution": analytics.get("company_distribution", {}),
    }

    ctx.workflow_variables["final_report"] = json.dumps(report, indent=2)
    return ctx
