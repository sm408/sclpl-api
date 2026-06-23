"""FastAPI application factory.

Provides create_app(db_path) which returns a fully configured FastAPI
instance with lifespan management, security headers, loopback
validation, and the API router tree.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.engine.event_bus import SimpleEventBus
from app.services.collection_service import CollectionRepository, RequestRepository
from app.services.environment_service import EnvironmentRepository
from app.services.history_service import HistoryRepository
from app.services.operation_registry import OperationRegistry
from app.services.project_service import ProjectRepository
from app.services.request_executor import HttpRequestExecutor
from app.services.workflow_service import WorkflowRepository
from app.storage.db import Database
from app.web.api.collections import router as collections_router
from app.web.api.commands import router as commands_router
from app.web.api.environments import router as environments_router
from app.web.api.functions import router as functions_router
from app.web.api.health import router as health_router
from app.web.api.history import router as history_router
from app.web.api.licenses import router as licenses_router
from app.web.api.logs import router as logs_router
from app.web.api.operations import router as operations_router
from app.web.api.plugins import router as plugins_router
from app.web.api.projects import router as projects_router
from app.web.api.requests import router as requests_router
from app.web.api.settings import router as settings_router
from app.web.api.workflows import router as workflows_router
from app.web.deps import ServiceContainer
from app.web.errors import register_error_handlers
from app.web.sse import SSEManager

logger = logging.getLogger(__name__)

# ── Correlation ID ──────────────────────────────────────────────────────

CORRELATION_ID_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Generate or accept a correlation ID for every request.

    If the incoming request carries an ``X-Correlation-ID`` header its
    value is reused; otherwise a new 12-char hex ID is generated.
    The ID is stored on ``request.state.correlation_id`` and echoed
    back in the response header.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        cid = request.headers.get(CORRELATION_ID_HEADER) or uuid.uuid4().hex[:12]
        request.state.correlation_id = cid
        response = await call_next(request)
        response.headers[CORRELATION_ID_HEADER] = cid
        return response


# ── Security headers ────────────────────────────────────────────────────

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self' http://127.0.0.1:* http://localhost:*; "
        "worker-src 'self' blob:"
    ),
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security headers to every response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        for key, value in SECURITY_HEADERS.items():
            response.headers[key] = value
        return response


class HostValidationMiddleware(BaseHTTPMiddleware):
    """Reject requests with an unrecognised Host header.

    In production (loopback binding) we only accept requests whose
    Host header resolves to 127.0.0.1 / localhost.  This prevents
    DNS-rebinding attacks against /docs and /openapi.json.
    """

    def __init__(self, app, allowed_hosts: set[str] | None = None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._allowed = allowed_hosts or {
            "127.0.0.1", "localhost",
            "127.0.0.1:8420", "localhost:8420",
        }

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        host = request.headers.get("host", "")
        # Strip port for comparison
        hostname = host.split(":")[0] if host else ""
        if hostname and hostname not in {"127.0.0.1", "localhost"}:
            cid = getattr(request.state, "correlation_id", "")
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "code": "BAD_REQUEST",
                        "message": "Invalid Host header.",
                        "fieldErrors": [],
                        "correlationId": cid,
                    }
                },
            )
        return await call_next(request)


class LoopbackOnlyMiddleware(BaseHTTPMiddleware):
    """Restrict /docs and /openapi.json to loopback connections only."""

    _PROTECTED = {"/docs", "/redoc", "/openapi.json"}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in self._PROTECTED:
            client = request.client
            if client and client.host not in {"127.0.0.1", "::1", "localhost"}:
                cid = getattr(request.state, "correlation_id", "")
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": "FORBIDDEN",
                            "message": (
                                "Documentation endpoints are only "
                                "accessible from localhost."
                            ),
                            "fieldErrors": [],
                            "correlationId": cid,
                        }
                    },
                )
        return await call_next(request)


# ── Lifespan ────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle.

    Startup:
    - Create and initialize the Database (runs migrations)
    - Build the ServiceContainer
    - Start the EventBus and MonitorRunner infrastructure
    - Schedule periodic cleanup of terminal operations
    - Store everything on app.state

    Shutdown:
    - Stop the cleanup task
    - Stop all monitor tasks
    - Close the database
    """
    import asyncio

    db_path: str = app.state.db_path
    db = Database(db_path)
    await db.connect()
    await db.initialize()

    # Build service container
    data_root = (
        Path(db_path).parent.parent if "projects" in db_path else Path("data")
    )
    event_bus = SimpleEventBus()
    project_repo = ProjectRepository(db, data_root=data_root)
    collection_repo = CollectionRepository(db)
    request_repo = RequestRepository(db)
    environment_repo = EnvironmentRepository(db)
    history_repo = HistoryRepository(db)
    workflow_repo = WorkflowRepository(db)
    executor = HttpRequestExecutor()
    operation_registry = OperationRegistry()
    sse_manager = SSEManager()

    services = ServiceContainer(
        db=db,
        projects=project_repo,
        collections=collection_repo,
        requests=request_repo,
        environments=environment_repo,
        history=history_repo,
        workflows=workflow_repo,
        executor=executor,
        operations=operation_registry,
        sse=sse_manager,
    )

    app.state.db = db
    app.state.services = services
    app.state.event_bus = event_bus

    # Schedule periodic cleanup of expired terminal operations
    async def _cleanup_loop() -> None:
        while True:
            await asyncio.sleep(300)  # every 5 minutes
            try:
                removed = await operation_registry.cleanup_terminal()
                if removed:
                    logger.info("Cleaned up %d expired terminal operations", removed)
            except Exception:
                logger.exception("Error during operation cleanup")

    cleanup_task = asyncio.create_task(_cleanup_loop())

    logger.info("Web API started — database at %s", db_path)

    yield  # ── app is running ──

    # Shutdown
    logger.info("Web API shutting down")
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    await sse_manager.shutdown()
    await db.close()


# ── Application factory ─────────────────────────────────────────────────


def create_app(
    db_path: str | Path = "data/sclplapi.db",
    *,
    debug: bool = False,
) -> FastAPI:
    """Build and return a configured FastAPI application."""
    app = FastAPI(
        title="SCLPLAPI",
        description="Local-first API workflow studio",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.state.db_path = str(db_path)

    # Middleware (executed in reverse order of addition)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(LoopbackOnlyMiddleware)
    app.add_middleware(HostValidationMiddleware)
    app.add_middleware(CorrelationIdMiddleware)

    # Error handlers
    register_error_handlers(app)

    # Routers
    app.include_router(health_router)
    app.include_router(projects_router)
    app.include_router(collections_router)
    app.include_router(requests_router)
    app.include_router(environments_router)
    app.include_router(history_router)
    app.include_router(workflows_router)
    app.include_router(functions_router)
    app.include_router(plugins_router)
    app.include_router(operations_router)
    app.include_router(settings_router)
    app.include_router(logs_router)
    app.include_router(licenses_router)
    app.include_router(commands_router)

    # ── Static file serving for the Vue SPA ──────────────────────────
    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        # Hashed assets get immutable cache headers
        assets_dir = static_dir / "assets"
        if assets_dir.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=str(assets_dir)),
                name="static-assets",
            )

        # SPA catch-all: serve index.html for all non-API, non-asset routes
        @app.get("/{path:path}", include_in_schema=False, response_model=None)
        async def spa_fallback(path: str) -> Response:
            """Serve the SPA index.html for client-side routing.

            Any path that is not matched by an API router or static file
            mount falls through here. The Vue router handles the path
            on the client side.

            API routes (starting with /api/) that don't match any defined
            endpoint return a proper 404 instead of the SPA.
            """
            if path.startswith("api/"):
                cid = uuid.uuid4().hex[:12]
                return JSONResponse(
                    status_code=404,
                    content={
                        "error": {
                            "code": "NOT_FOUND",
                            "message": f"API route '/{path}' not found.",
                            "fieldErrors": [],
                            "correlationId": cid,
                        }
                    },
                )
            index = static_dir / "index.html"
            return FileResponse(
                str(index),
                headers={"Cache-Control": "no-cache"},
            )

    return app
