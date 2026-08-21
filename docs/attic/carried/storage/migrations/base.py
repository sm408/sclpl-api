from __future__ import annotations

from abc import ABC, abstractmethod


class Migration(ABC):
    @property
    @abstractmethod
    def version(self) -> int: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    async def up(self, db) -> None: ...

    @abstractmethod
    async def down(self, db) -> None: ...
