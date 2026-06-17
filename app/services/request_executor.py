from __future__ import annotations

import time
import uuid
from typing import Any

import httpx

from app.core.contracts.request_executor import RequestExecutor, ResponseResult
from app.core.contracts.variable_resolver import VariableResolver
from app.core.engine.auth import build_auth
from app.core.engine.variable_resolver import DefaultVariableResolver
from app.core.models.context import ExecutionContext
from app.core.models.history import HistoryEntry, RunStatus
from app.core.models.request import RequestDef


class HttpRequestExecutor(RequestExecutor):
    def __init__(self, resolver: VariableResolver | None = None) -> None:
        self._resolver = resolver or DefaultVariableResolver()

    async def execute(
        self,
        request: RequestDef,
        ctx: ExecutionContext,
    ) -> ResponseResult:
        url = self._resolver.resolve(request.url, ctx)
        headers = self._build_headers(request, ctx)
        params = self._build_params(request, ctx)
        body = self._resolver.resolve(request.body, ctx) if request.body else None

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method=request.method.value,
                    url=url,
                    headers=headers,
                    params=params,
                    content=body,
                )
                elapsed = int((time.monotonic() - start) * 1000)
                return ResponseResult(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=response.text,
                    duration_ms=elapsed,
                )
        except httpx.TimeoutException:
            elapsed = int((time.monotonic() - start) * 1000)
            return ResponseResult(
                status_code=0,
                headers={},
                body="",
                duration_ms=elapsed,
                error="Request timed out",
            )
        except httpx.RequestError as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            return ResponseResult(
                status_code=0,
                headers={},
                body="",
                duration_ms=elapsed,
                error=str(exc),
            )

    async def execute_with_history(
        self,
        request: RequestDef,
        ctx: ExecutionContext,
    ) -> tuple[ResponseResult, HistoryEntry]:
        result = await self.execute(request, ctx)

        status = RunStatus.ERROR if result.error or result.status_code >= 400 else RunStatus.SUCCESS
        if result.error and "timed out" in result.error:
            status = RunStatus.TIMEOUT

        entry = HistoryEntry(
            id=str(uuid.uuid4()),
            request_id=request.id,
            request_name=request.name,
            method=request.method.value,
            url=request.url,
            status=status,
            status_code=result.status_code,
            response_body=result.body[:10000] if result.body else None,
            response_headers=result.headers,
            duration_ms=result.duration_ms,
            error_message=result.error,
            environment_id=ctx.environment.id if ctx.environment else None,
            variables_used=dict(ctx.variables),
        )

        return result, entry

    def _build_headers(self, request: RequestDef, ctx: ExecutionContext) -> dict[str, str]:
        headers: dict[str, str] = {}
        for h in request.headers:
            if h.enabled:
                headers[self._resolver.resolve(h.key, ctx)] = self._resolver.resolve(
                    h.value, ctx
                )
        auth = build_auth(request.auth_type, request.auth_config)
        if auth:
            headers = auth.apply_to_headers(headers)
        return headers

    def _build_params(
        self, request: RequestDef, ctx: ExecutionContext
    ) -> dict[str, str]:
        params: dict[str, str] = {}
        for p in request.query_params:
            if p.enabled:
                params[self._resolver.resolve(p.key, ctx)] = self._resolver.resolve(
                    p.value, ctx
                )
        return params
