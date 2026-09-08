from __future__ import annotations

import pytest

from plugins.azure_blob.provider import AzureBlobProvider, parse_uri
from sclpl.ext.resources import ResourceInvalidURI


def test_azure_uri_parsing_and_redaction() -> None:
    uri = parse_uri("azblob://Account/container/a/path.csv?sig=secret")
    assert (uri.account, uri.container, uri.blob) == ("Account", "container", "a/path.csv")
    assert AzureBlobProvider().display_uri("azblob://Account/container/a.csv?sig=secret") == (
        "azblob://Account/container/a.csv"
    )


def test_azure_uri_requires_account_and_container() -> None:
    with pytest.raises(ResourceInvalidURI):
        parse_uri("azblob://account")


def test_azure_provider_declares_safe_resource_capabilities() -> None:
    capabilities = AzureBlobProvider().capabilities()
    assert capabilities.write and capabilities.list and capabilities.conditional_write
