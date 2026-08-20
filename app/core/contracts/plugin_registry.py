from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.models.plugin import PluginInfo


class PluginRegistry(ABC):
    @abstractmethod
    def discover(self) -> list[PluginInfo]:
        ...

    @abstractmethod
    def load(self, name: str) -> PluginInfo:
        ...

    @abstractmethod
    def unload(self, name: str) -> bool:
        ...

    @abstractmethod
    def list_plugins(self) -> list[PluginInfo]:
        ...

    @abstractmethod
    def get_plugin(self, name: str) -> PluginInfo | None:
        ...
