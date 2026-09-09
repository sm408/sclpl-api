"""Async resource-provider contract and a safe adapter for synchronous providers."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import BinaryIO, Protocol

from sclpl.ext.resources import ResourceCapabilities, ResourceInfo, ResourceProvider


class AsyncResourceProvider(Protocol):
    """Async form of the stable resource contract; URI work remains synchronous."""

    scheme: str

    def capabilities(self) -> ResourceCapabilities: ...
    def normalize(self, uri: str) -> str: ...
    def resolve(self, base_uri: str, reference: str) -> str: ...
    def display_uri(self, uri: str) -> str: ...
    async def stat(self, uri: str) -> ResourceInfo: ...
    async def exists(self, uri: str) -> bool: ...
    async def list(self, uri: str) -> Iterable[ResourceInfo]: ...
    async def download(self, uri: str, target: BinaryIO) -> ResourceInfo: ...
    async def upload(
        self,
        source: BinaryIO,
        uri: str,
        *,
        overwrite: bool = False,
        expected_revision: str | None = None,
    ) -> ResourceInfo: ...


class ThreadedResourceProvider:
    """Run a synchronous provider off the event loop under the async contract."""

    def __init__(self, provider: ResourceProvider) -> None:
        self.provider = provider
        self.scheme = provider.scheme

    def capabilities(self) -> ResourceCapabilities:
        return self.provider.capabilities()

    def normalize(self, uri: str) -> str:
        return self.provider.normalize(uri)

    def resolve(self, base_uri: str, reference: str) -> str:
        return self.provider.resolve(base_uri, reference)

    def display_uri(self, uri: str) -> str:
        return self.provider.display_uri(uri)

    async def stat(self, uri: str) -> ResourceInfo:
        return await asyncio.to_thread(self.provider.stat, uri)

    async def exists(self, uri: str) -> bool:
        return await asyncio.to_thread(self.provider.exists, uri)

    async def list(self, uri: str) -> Iterable[ResourceInfo]:
        return await asyncio.to_thread(lambda: tuple(self.provider.list(uri)))

    async def download(self, uri: str, target: BinaryIO) -> ResourceInfo:
        return await asyncio.to_thread(self.provider.download, uri, target)

    async def upload(
        self,
        source: BinaryIO,
        uri: str,
        *,
        overwrite: bool = False,
        expected_revision: str | None = None,
    ) -> ResourceInfo:
        return await asyncio.to_thread(
            self.provider.upload,
            source,
            uri,
            overwrite=overwrite,
            expected_revision=expected_revision,
        )
