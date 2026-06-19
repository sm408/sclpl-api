"""
@name: hello_world
@type: utility
@description: A simple greeting function that returns a hello message
"""


def run(ctx):
    name = ctx.workflow_variables.get("name", "World")
    return {"message": f"Hello, {name}!", "plugin": "sample-api-plugin"}
