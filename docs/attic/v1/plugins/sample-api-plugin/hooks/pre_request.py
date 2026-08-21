"""
@name: plugin_pre_request
@type: pre_request
@description: Adds plugin headers to outgoing requests
"""


async def run(ctx):
    if ctx.request:
        from app.core.models.request import RequestParam
        ctx.request.headers.append(RequestParam(key="X-Plugin", value="sample-api-plugin"))
        ctx.request.headers.append(RequestParam(key="X-Plugin-Version", value="1.0.0"))
    return ctx
