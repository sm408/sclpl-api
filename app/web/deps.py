"""FastAPI dependency injection.

Provides the Database, repositories, and service instances as
request-scoped dependencies.  Route handlers must never instantiate
databases or engines directly.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass

from fastapi import Request

from app.services.project_service import ProjectRepository
from app.storage.db import Database


@dataclass(frozen=True)
class ServiceContainer:
    """Bundles every repository / service that the API needs."""

    db: Database
    projects: ProjectRepository


async def _get_db(request: Request) -> AsyncGenerator[Database, None]:
    """Yield the shared Database from app state."""
    yield request.app.state.db


async def _get_project_repo(request: Request) -> ProjectRepository:
    return request.app.state.services.projects
