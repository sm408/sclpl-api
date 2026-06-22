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
from app.services.monitor_service import MonitorService
from app.services.monitor_runner import MonitorRunner
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
        self.monitors = MonitorService(self.db)
        self.monitor_runner = MonitorRunner(self.monitors, self.event_bus)

        self.plugin_registry = None
        self._init_plugins()

    def _init_plugins(self) -> None:
        """Initialize plugin registry and discover plugins."""
        try:
            from app.core.engine.plugin_registry import FilesystemPluginRegistry
            self.plugin_registry = FilesystemPluginRegistry()
            discovered = self.plugin_registry.discover()
            if discovered:
                loaded = [p for p in discovered if p.status.value == "active"]
                logger.info("Discovered %d plugins (%d loaded)", len(discovered), len(loaded))
        except Exception as exc:
            logger.warning("Plugin system initialization failed: %s", exc)

    def get_plugin_functions(self) -> list[dict[str, str]]:
        """Get all functions from loaded plugins."""
        if not self.plugin_registry:
            return []
        return self.plugin_registry.get_all_functions()

    def get_plugin_variables(self) -> dict[str, str]:
        """Get all variables from loaded plugins."""
        if not self.plugin_registry:
            return {}
        return self.plugin_registry.get_all_variables()

    async def start(self) -> None:
        await self.db.connect()
        await self.db.initialize()
        # Start monitor runner
        await self.monitor_runner.start()
        logger.info("SCLPLAPI started")

    async def stop(self) -> None:
        # Stop monitor runner
        await self.monitor_runner.stop()
        await self.db.close()
        logger.info("SCLPLAPI stopped")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()
