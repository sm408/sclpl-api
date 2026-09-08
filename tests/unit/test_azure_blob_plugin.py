from __future__ import annotations

import pytest

from plugins.azure_blob.provider import AzureBlobProvider, parse_uri
from sclpl.ext.resources import ResourceAuthenticationError, ResourceInvalidURI


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


def test_azure_default_auth_uses_configurable_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class Client:
        def __init__(self, url: str, credential: object) -> None:
            captured.update(url=url, credential=credential)

    class DefaultCredential:
        def __init__(self, **kwargs: str) -> None:
            captured["credential_kwargs"] = kwargs

    monkeypatch.setattr(
        AzureBlobProvider, "_imports", staticmethod(lambda: (DefaultCredential, Client, None))
    )
    provider = AzureBlobProvider(
        environment={"SCLPL_AZURE_BLOB_ACCOUNT_URL": "https://{account}.privatelink.blob.core.windows.net"}
    )
    provider._service("orders")
    assert captured["url"] == "https://orders.privatelink.blob.core.windows.net"
    assert isinstance(captured["credential"], DefaultCredential)
    assert captured["credential_kwargs"] == {}


def test_azure_default_auth_accepts_an_explicit_managed_identity_client_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class Client:
        def __init__(self, url: str, credential: object) -> None:
            del url
            captured["credential"] = credential

    class DefaultCredential:
        def __init__(self, **kwargs: str) -> None:
            captured["kwargs"] = kwargs

    monkeypatch.setattr(
        AzureBlobProvider, "_imports", staticmethod(lambda: (DefaultCredential, Client, None))
    )
    AzureBlobProvider(
        environment={"SCLPL_AZURE_BLOB_MANAGED_IDENTITY_CLIENT_ID": "client-id"}
    )._service("account")
    assert captured["kwargs"] == {"managed_identity_client_id": "client-id"}


def test_azure_auth_requires_secret_for_selected_mode() -> None:
    provider = AzureBlobProvider(environment={"SCLPL_AZURE_BLOB_AUTH": "sas"})
    with pytest.raises(ResourceAuthenticationError, match="SAS_TOKEN"):
        provider._secret("SAS_TOKEN")


def test_azure_explicit_auth_modes_select_the_expected_client_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Client:
        def __init__(self, url: str, credential: object) -> None:
            self.url, self.credential = url, credential

        @classmethod
        def from_connection_string(cls, value: str) -> object:
            return ("connection-string", value)

    class SasCredential:
        def __init__(self, value: str) -> None:
            self.value = value

    monkeypatch.setattr(
        AzureBlobProvider, "_imports", staticmethod(lambda: (object, Client, SasCredential))
    )

    connection = AzureBlobProvider(
        environment={
            "SCLPL_AZURE_BLOB_AUTH": "connection-string",
            "SCLPL_AZURE_BLOB_CONNECTION_STRING": "UseDevelopmentStorage=true",
        }
    )._service("ignored")
    assert connection == ("connection-string", "UseDevelopmentStorage=true")

    key = AzureBlobProvider(
        environment={"SCLPL_AZURE_BLOB_AUTH": "account-key", "SCLPL_AZURE_BLOB_ACCOUNT_KEY": "key"}
    )._service("account")
    assert isinstance(key, Client) and key.credential == "key"

    sas = AzureBlobProvider(
        environment={"SCLPL_AZURE_BLOB_AUTH": "sas", "SCLPL_AZURE_BLOB_SAS_TOKEN": "?sig=value"}
    )._service("account")
    assert isinstance(sas, Client) and isinstance(sas.credential, SasCredential)
    assert sas.credential.value == "sig=value"

    custom_credential = object()
    custom = AzureBlobProvider(
        environment={"SCLPL_AZURE_BLOB_AUTH": "custom"},
        credential_factory=lambda account: custom_credential,
    )._service("account")
    assert isinstance(custom, Client) and custom.credential is custom_credential

    with pytest.raises(ResourceAuthenticationError, match="must be one of"):
        AzureBlobProvider(environment={"SCLPL_AZURE_BLOB_AUTH": "unsupported"})._service("account")


def test_azure_sdk_errors_redact_configured_credentials() -> None:
    provider = AzureBlobProvider(
        environment={
            "SCLPL_AZURE_BLOB_ACCOUNT_KEY": "account-key-secret",
            "SCLPL_AZURE_BLOB_SAS_TOKEN": "sas-secret",
        }
    )
    rendered = str(provider._translate(Exception("failed account-key-secret sas-secret"), "azblob://a/c/x"))
    assert "account-key-secret" not in rendered
    assert "sas-secret" not in rendered
    assert rendered.count("[redacted]") == 2
