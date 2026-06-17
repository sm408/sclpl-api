"""
@name: Log Response
@type: post_response
@version: 1
"""

import logging

logger = logging.getLogger(__name__)


def run(ctx):
    if ctx.response:
        logger.info(
            "Response: %s %s -> %s",
            ctx.request.method if ctx.request else "?",
            ctx.request.url if ctx.request else "?",
            getattr(ctx.response, "status_code", "?"),
        )
    return ctx
