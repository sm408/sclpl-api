"""
@name: plugin_post_response
@type: post_response
@description: Logs response metadata from plugin-extended requests
"""


async def run(ctx):
    response = ctx.metadata.get("response")
    if response:
        ctx.metadata["plugin_processed"] = True
        ctx.metadata["plugin_response_status"] = getattr(response, "status_code", None)
    return ctx
