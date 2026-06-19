"""
@name: csv_converter
@type: transformer
@version: 1
@description: Convert JSON data to CSV format

Config via workflow_variables: csv_source (step output key),
csv_delimiter (default comma), csv_include_header (true/false).
"""

import csv
import io
import json


def run(ctx):
    source_key = ctx.workflow_variables.get("csv_source", "")
    delimiter = ctx.workflow_variables.get("csv_delimiter", ",")
    include_header = ctx.workflow_variables.get("csv_include_header", "true").lower() == "true"

    data = ctx.workflow_variables.get(source_key) if source_key else None
    if data is None:
        data = ctx.step_outputs.get(source_key, []) if source_key else []

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return {"success": False, "error": "Source data is not valid JSON"}

    if not isinstance(data, list):
        data = [data]

    if not data:
        return {"success": True, "csv": "", "row_count": 0}

    headers = []
    for item in data:
        if isinstance(item, dict):
            for key in item:
                if key not in headers:
                    headers.append(key)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, delimiter=delimiter)

    if include_header:
        writer.writeheader()

    for item in data:
        if isinstance(item, dict):
            writer.writerow(item)

    csv_content = output.getvalue()
    ctx.workflow_variables["csv_output"] = csv_content

    return {
        "success": True,
        "csv": csv_content,
        "row_count": len(data),
        "column_count": len(headers),
    }
