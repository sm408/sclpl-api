from __future__ import annotations

import logging

from app.storage.migrations.base import Migration

logger = logging.getLogger(__name__)


class MigrationRunner:
    def __init__(self, db, migrations: list[Migration]) -> None:
        self._db = db
        self._migrations = sorted(migrations, key=lambda m: m.version)

    async def current_version(self) -> int:
        row = await self._db.fetch_one(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        )
        return row["version"] if row else 0

    async def run_pending(self) -> list[int]:
        current = await self.current_version()
        applied: list[int] = []

        for migration in self._migrations:
            if migration.version > current:
                logger.info(
                    "Applying migration %d: %s", migration.version, migration.description
                )
                await migration.up(self._db)
                await self._db.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (migration.version,),
                )
                await self._db.commit()
                applied.append(migration.version)

        return applied

    async def rollback_to(self, target_version: int) -> list[int]:
        current = await self.current_version()
        rolled_back: list[int] = []

        for migration in reversed(self._migrations):
            if migration.version > target_version and migration.version <= current:
                logger.info(
                    "Rolling back migration %d: %s", migration.version, migration.description
                )
                await migration.down(self._db)
                await self._db.execute(
                    "DELETE FROM schema_version WHERE version = ?",
                    (migration.version,),
                )
                await self._db.commit()
                rolled_back.append(migration.version)

        return rolled_back
