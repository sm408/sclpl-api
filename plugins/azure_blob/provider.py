"""Azure Blob implementation of SCLPL's public resource-provider contract."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, BinaryIO
from urllib.parse import urlsplit, urlunsplit

from sclpl.ext.api import (
    ResourceCapabilities,
    ResourceAuthenticationError,
    ResourceConflict,
    ResourceInfo,
    ResourceInvalidURI,
    ResourceNotFound,
    ResourcePermissionDenied,
    ResourceUnavailable,
    SclplError,
)


@dataclass(frozen=True, slots=True)
class AzureBlobURI:
    account: str
    container: str
    blob: str

    @property
    def account_url(self) -> str:
        return f"https://{self.account}.blob.core.windows.net"


def parse_uri(uri: str) -> AzureBlobURI:
    parsed = urlsplit(uri)
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.scheme.lower() != "azblob" or not parsed.netloc or not parts:
        raise ResourceInvalidURI("azblob URI must be azblob://<account>/<container>/<blob>")
    return AzureBlobURI(parsed.netloc, parts[0], "/".join(parts[1:]))


class AzureBlobProvider:
    scheme = "azblob"

    def capabilities(self) -> ResourceCapabilities:
        return ResourceCapabilities(write=True, list=True, revisions=True, conditional_write=True)

    def normalize(self, uri: str) -> str:
        parsed = urlsplit(uri)
        details = parse_uri(uri)
        path = f"/{details.container}" + (f"/{details.blob}" if details.blob else "")
        return urlunsplit(("azblob", details.account.lower(), path, parsed.query, ""))

    def resolve(self, base_uri: str, reference: str) -> str:
        if "://" in reference:
            return self.normalize(reference)
        return self.normalize(f"{base_uri.rstrip('/')}/{reference.lstrip('/')}")

    def stat(self, uri: str) -> ResourceInfo:
        client = self._blob(uri)
        try:
            props = client.get_blob_properties()
        except Exception as error:  # Azure SDK is optional and translated here.
            raise self._translate(error, uri) from error
        return self._info(uri, props)

    def exists(self, uri: str) -> bool:
        try:
            return bool(self._blob(uri).exists())
        except Exception as error:
            mapped = self._translate(error, uri)
            if isinstance(mapped, ResourceNotFound):
                return False
            raise mapped from error

    def list(self, uri: str) -> Iterable[ResourceInfo]:
        details = parse_uri(uri)
        try:
            container = self._service(details.account).get_container_client(details.container)
            return [
                ResourceInfo(
                    uri=self.normalize(f"azblob://{details.account}/{details.container}/{item.name}"),
                    size=getattr(item, "size", None),
                    modified=getattr(item, "last_modified", None),
                    revision=getattr(item, "etag", None),
                    content_type=getattr(getattr(item, "content_settings", None), "content_type", None),
                )
                for item in container.list_blobs(name_starts_with=details.blob)
            ]
        except Exception as error:
            raise self._translate(error, uri) from error

    def download(self, uri: str, target: BinaryIO) -> ResourceInfo:
        try:
            client = self._blob(uri)
            downloader = client.download_blob()
            downloader.readinto(target)
            return self._info(uri, client.get_blob_properties())
        except Exception as error:
            raise self._translate(error, uri) from error

    def upload(self, source: BinaryIO, uri: str, *, overwrite: bool = False, expected_revision: str | None = None) -> ResourceInfo:
        try:
            client = self._blob(uri)
            kwargs: dict[str, Any] = {"overwrite": overwrite}
            if expected_revision is not None:
                from azure.core import MatchConditions

                kwargs.update(etag=expected_revision, match_condition=MatchConditions.IfNotModified)
            elif not overwrite:
                kwargs["overwrite"] = False
            client.upload_blob(source, **kwargs)
            return self._info(uri, client.get_blob_properties())
        except Exception as error:
            raise self._translate(error, uri) from error

    def display_uri(self, uri: str) -> str:
        parsed = urlsplit(uri)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))

    def _service(self, account: str) -> Any:
        try:
            from azure.identity import DefaultAzureCredential  # type: ignore[import-untyped]
            from azure.storage.blob import BlobServiceClient
        except ImportError as error:
            raise ResourceUnavailable("azblob requires: pip install sclpl-azure-blob") from error
        return BlobServiceClient(f"https://{account}.blob.core.windows.net", credential=DefaultAzureCredential())

    def _blob(self, uri: str) -> Any:
        details = parse_uri(uri)
        if not details.blob:
            raise ResourceInvalidURI("azblob operation requires a blob, not only a container")
        return self._service(details.account).get_blob_client(details.container, details.blob)

    def _info(self, uri: str, props: Any) -> ResourceInfo:
        return ResourceInfo(
            uri=self.normalize(uri), size=getattr(props, "size", None),
            modified=getattr(props, "last_modified", None), revision=getattr(props, "etag", None),
            content_type=getattr(getattr(props, "content_settings", None), "content_type", None),
        )

    def _translate(self, error: Exception, uri: str) -> SclplError:
        status = getattr(error, "status_code", None)
        message = f"Azure Blob {self.display_uri(uri)}: {error}"
        if status == 404:
            return ResourceNotFound(message)
        if status in (401,):
            return ResourceAuthenticationError(message)
        if status == 403:
            return ResourcePermissionDenied(message)
        if status in (409, 412):
            return ResourceConflict(message)
        return ResourceUnavailable(message)
