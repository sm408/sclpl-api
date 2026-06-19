"""
@name: Load Data
@type: transformer
@version: 1

Template for the load stage of a data pipeline.
Combines transformed datasets into a final output structure.
"""

import json
from datetime import datetime, timezone


def run(ctx):
    datasets = {}

    for key, value in ctx.workflow_variables.items():
        if key.startswith("transformed_"):
            data = json.loads(value) if isinstance(value, str) else value
            datasets[key] = data

    total_records = sum(d.get("record_count", 0) for d in datasets.values())

    result = {
        "pipeline": "data-pipeline",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "stages_completed": len(datasets),
        "total_records_processed": total_records,
        "datasets": {
            k: {"record_count": v.get("record_count", 0), "transformed": v.get("transformed", False)}
            for k, v in datasets.items()
        },
        "status": "success",
    }

    ctx.workflow_variables["final_output"] = json.dumps(result, indent=2)
    return ctx
