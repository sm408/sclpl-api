from __future__ import annotations

import csv
from io import StringIO

from app.core.models.context import ExecutionContext
from app.core.models.request import RequestDef
from app.services.request_executor import HttpRequestExecutor


class BatchRunner:
    def __init__(self, executor: HttpRequestExecutor | None = None) -> None:
        self._executor = executor or HttpRequestExecutor()

    async def run_csv_batch(
        self,
        request: RequestDef,
        csv_content: str,
        base_ctx: ExecutionContext,
    ) -> list[tuple[dict[str, str], any]]:
        reader = csv.DictReader(StringIO(csv_content))
        results: list[tuple[dict[str, str], any]] = []

        for row in reader:
            ctx = ExecutionContext(
                request=base_ctx.request,
                environment=base_ctx.environment,
                variables=dict(base_ctx.variables),
                batch_row=dict(row),
                workflow_variables=dict(base_ctx.workflow_variables),
                metadata=dict(base_ctx.metadata),
            )
            result = await self._executor.execute(request, ctx)
            results.append((dict(row), result))

        return results
