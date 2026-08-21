"""
@name: transform_data
@type: transformer
@description: Transforms input data by applying uppercase and adding metadata
"""


def run(ctx):
    data = ctx.workflow_variables.get("input_data", "")
    if isinstance(data, str):
        transformed = data.upper()
    elif isinstance(data, dict):
        transformed = {k: str(v).upper() for k, v in data.items()}
    else:
        transformed = str(data).upper()

    return {
        "original": data,
        "transformed": transformed,
        "transformed_by": "sample-api-plugin",
        "timestamp": __import__("time").time(),
    }
