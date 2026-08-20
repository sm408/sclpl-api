from __future__ import annotations

import logging

from app.core.contracts.function_runner import FunctionRunner
from app.core.engine.function_runner import FilesystemFunctionRunner
from app.core.models.context import ExecutionContext

logger = logging.getLogger(__name__)


class FunctionHookRunner:
    def __init__(self, runner: FunctionRunner | None = None) -> None:
        self._runner = runner or FilesystemFunctionRunner()

    async def run_pre_request(self, ctx: ExecutionContext) -> ExecutionContext:
        functions = self._runner.discover()
        pre_request_funcs = [f for f in functions if f.get("type") == "pre_request"]

        for func_meta in pre_request_funcs:
            name = func_meta.get("name", "")
            logger.debug("Running pre-request function: %s", name)
            result = await self._runner.run(name, ctx)
            if result.success and result.return_value is not None:
                ctx = result.return_value
            elif result.error:
                logger.warning("Pre-request function %s failed: %s", name, result.error)

        return ctx

    async def run_post_response(self, ctx: ExecutionContext) -> ExecutionContext:
        functions = self._runner.discover()
        post_response_funcs = [f for f in functions if f.get("type") == "post_response"]

        for func_meta in post_response_funcs:
            name = func_meta.get("name", "")
            logger.debug("Running post-response function: %s", name)
            result = await self._runner.run(name, ctx)
            if result.success and result.return_value is not None:
                ctx = result.return_value
            elif result.error:
                logger.warning("Post-response function %s failed: %s", name, result.error)

        return ctx
