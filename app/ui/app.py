from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.core.engine.event_bus import SimpleEventBus
from app.core.engine.variable_resolver import DefaultVariableResolver
from app.services.collection_service import CollectionRepository, RequestRepository
from app.services.environment_service import EnvironmentRepository
from app.services.export_service import DefaultExportPipeline
from app.services.history_service import HistoryRepository
from app.services.request_executor import HttpRequestExecutor
from app.storage.db import Database

logger = logging.getLogger(__name__)


class App:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db = Database(db_path)
        self.event_bus = SimpleEventBus()
        self.variable_resolver = DefaultVariableResolver()
        self.request_executor = HttpRequestExecutor(self.variable_resolver)
        self.export_pipeline = DefaultExportPipeline()

        self.collections = CollectionRepository(self.db)
        self.requests = RequestRepository(self.db)
        self.environments = EnvironmentRepository(self.db)
        self.history = HistoryRepository(self.db)

    async def start(self) -> None:
        await self.db.connect()
        await self.db.initialize()
        logger.info("SCLPLAPI started")

    async def stop(self) -> None:
        await self.db.close()
        logger.info("SCLPLAPI stopped")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()
