from __future__ import annotations

import pytest

from plugins.azure_blob.provider import AzureBlobProvider, parse_uri
from sclpl.ext.resources import ResourceAuthenticationError, ResourceInvalidURI, ResourceUnavailable


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
    assert (
        capabilities.write
        and capabilities.list
        and capabilities.conditional_write
        and capabilities.locks
        and capabilities.server_copy
    )


def test_azure_server_side_copy_waits_for_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    copied: dict[str, object] = {}

    class Properties:
        copy = None
        size = 2
        last_modified = None
        etag = "copied"
        content_settings = None
        metadata = None

    class Destination:
        def start_copy_from_url(self, source: str, **kwargs: object) -> None:
            copied.update(source=source, **kwargs)

        def get_blob_properties(self) -> Properties:
            return Properties()

    provider = AzureBlobProvider()
    monkeypatch.setattr(provider, "_blob", lambda uri: Destination())
    info = provider.copy(
        "azblob://source/container/input file.csv?sig=token",
        "azblob://destination/container/output.csv",
    )

    assert copied["source"] == (
        "https://source.blob.core.windows.net/container/input%20file.csv?sig=token"
    )
    assert copied["if_none_match"] == "*"
    assert info.revision == "copied"


def test_azure_blob_lease_acquires_and_releases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[object] = []

    class Lease:
        def __init__(self, blob: object) -> None:
            events.append(blob)

        def acquire(self, *, lease_duration: int) -> str:
            events.append(lease_duration)
            return "lease-id"

        def release(self) -> None:
            events.append("release")

    provider = AzureBlobProvider()
    monkeypatch.setattr(provider, "_blob", lambda uri: "blob-client")
    monkeypatch.setattr(provider, "_lease_import", lambda: Lease)
    with provider.acquire_lock("azblob://account/container/object.csv", lease_duration=30) as lease:
        assert lease.uri == "azblob://account/container/object.csv"
        assert lease.lease_id == "lease-id"
    assert events == ["blob-client", 30, "release"]

    with pytest.raises(ResourceInvalidURI, match="between 15 and 60"):
        provider.acquire_lock("azblob://account/container/object.csv", lease_duration=2)


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
        environment={
            "SCLPL_AZURE_BLOB_ACCOUNT_URL": "https://{account}.privatelink.blob.core.windows.net"
        }
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
    rendered = str(
        provider._translate(Exception("failed account-key-secret sas-secret"), "azblob://a/c/x")
    )
    assert "account-key-secret" not in rendered
    assert "sas-secret" not in rendered
    assert rendered.count("[redacted]") == 2


def test_azure_transfer_concurrency_is_provider_scoped_and_validated() -> None:
    assert AzureBlobProvider(
        environment={"SCLPL_AZURE_BLOB_MAX_CONCURRENCY": "4"}
    )._transfer_options() == {"max_concurrency": 4}
    with pytest.raises(ResourceUnavailable, match="at least 1"):
        AzureBlobProvider(environment={"SCLPL_AZURE_BLOB_MAX_CONCURRENCY": "0"})._transfer_options()


def test_azure_resource_info_preserves_provider_metadata() -> None:
    class Properties:
        size = 1
        last_modified = None
        etag = "revision"
        content_settings = None
        metadata = {"owner": "analytics"}

    info = AzureBlobProvider()._info("azblob://account/container/object.csv", Properties())
    assert info.metadata == {"owner": "analytics"}


def test_azure_blob_client_preserves_version_or_snapshot_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class Service:
        def get_blob_client(self, container: str, blob: str, **kwargs: str) -> object:
            captured.update(container=container, blob=blob, **kwargs)
            return object()

    provider = AzureBlobProvider()
    monkeypatch.setattr(provider, "_service", lambda account: Service())
    provider._blob("azblob://account/container/object.csv?versionid=version-1")
    assert captured == {"container": "container", "blob": "object.csv", "version_id": "version-1"}
