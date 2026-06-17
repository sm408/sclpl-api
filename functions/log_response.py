"""
@name: Log Response
@type: post_response
@version: 1
"""

import logging

logger = logging.getLogger(__name__)


def run(ctx):
    response = ctx.metadata.get("response")
    if response:
        logger.info(
            "Response: %s %s -> %s (%dms)",
            ctx.request.method if ctx.request else "?",
            ctx.request.url if ctx.request else "?",
            getattr(response, "status_code", "?"),
            getattr(response, "duration_ms", 0),
        )
    return ctx
