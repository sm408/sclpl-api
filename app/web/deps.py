"""FastAPI dependency injection.

Provides the Database, repositories, and service instances as
request-scoped dependencies.  Route handlers must never instantiate
databases or engines directly.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass

from fastapi import Request

from app.services.collection_service import CollectionRepository, RequestRepository
from app.services.environment_service import EnvironmentRepository
from app.services.history_service import HistoryRepository
from app.services.operation_registry import OperationRegistry
from app.services.project_service import ProjectRepository
from app.services.request_executor import HttpRequestExecutor
from app.storage.db import Database
from app.web.sse import SSEManager


@dataclass(frozen=True)
class ServiceContainer:
    """Bundles every repository / service that the API needs."""

    db: Database
    projects: ProjectRepository
    collections: CollectionRepository
    requests: RequestRepository
    environments: EnvironmentRepository
    history: HistoryRepository
    executor: HttpRequestExecutor
    operations: OperationRegistry
    sse: SSEManager


async def _get_db(request: Request) -> AsyncGenerator[Database, None]:
    """Yield the shared Database from app state."""
    yield request.app.state.db


async def _get_project_repo(request: Request) -> ProjectRepository:
    return request.app.state.services.projects


async def _get_collection_repo(request: Request) -> CollectionRepository:
    return request.app.state.services.collections


async def _get_request_repo(request: Request) -> RequestRepository:
    return request.app.state.services.requests


async def _get_environment_repo(request: Request) -> EnvironmentRepository:
    return request.app.state.services.environments


async def _get_history_repo(request: Request) -> HistoryRepository:
    return request.app.state.services.history


async def _get_executor(request: Request) -> HttpRequestExecutor:
    return request.app.state.services.executor


async def _get_operation_registry(request: Request) -> OperationRegistry:
    return request.app.state.services.operations


async def _get_sse_manager(request: Request) -> SSEManager:
    return request.app.state.services.sse
