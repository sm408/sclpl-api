from __future__ import annotations

import base64

import pytest

from app.core.engine.auth import AuthConfig, build_auth


class TestAuthConfig:
    """Tests for AuthConfig.apply_to_headers() with various auth types."""

    def test_bearer_auth(self) -> None:
        """Bearer auth sets Authorization: Bearer <token>."""
        auth = AuthConfig(auth_type="bearer", config={"token": "mytoken123"})
        headers = auth.apply_to_headers({})
        assert headers["Authorization"] == "Bearer mytoken123"

    def test_bearer_auth_empty_token(self) -> None:
        """Bearer auth with empty token still sets the header."""
        auth = AuthConfig(auth_type="bearer", config={})
        headers = auth.apply_to_headers({})
        assert headers["Authorization"] == "Bearer "

    def test_basic_auth(self) -> None:
        """Basic auth sets Authorization: Basic <base64(user:password)>."""
        auth = AuthConfig(auth_type="basic", config={"username": "admin", "password": "secret"})
        headers = auth.apply_to_headers({})
        expected = base64.b64encode(b"admin:secret").decode()
        assert headers["Authorization"] == f"Basic {expected}"

    def test_basic_auth_empty_credentials(self) -> None:
        """Basic auth with empty credentials encodes an empty user:pass."""
        auth = AuthConfig(auth_type="basic", config={})
        headers = auth.apply_to_headers({})
        expected = base64.b64encode(b":").decode()
        assert headers["Authorization"] == f"Basic {expected}"

    def test_api_key_default_header(self) -> None:
        """API key auth defaults to X-API-Key header."""
        auth = AuthConfig(auth_type="api_key", config={"key": "abc123"})
        headers = auth.apply_to_headers({})
        assert headers["X-API-Key"] == "abc123"

    def test_api_key_custom_header(self) -> None:
        """API key auth uses custom header_name when specified."""
        auth = AuthConfig(auth_type="api_key", config={"key": "abc123", "header_name": "X-Custom-Auth"})
        headers = auth.apply_to_headers({})
        assert headers["X-Custom-Auth"] == "abc123"

    def test_api_key_empty_key(self) -> None:
        """API key auth with missing key sets empty value."""
        auth = AuthConfig(auth_type="api_key", config={})
        headers = auth.apply_to_headers({})
        assert headers["X-API-Key"] == ""

    def test_unknown_auth_type_returns_headers_unchanged(self) -> None:
        """An unrecognized auth_type does not modify headers."""
        auth = AuthConfig(auth_type="oauth2", config={"token": "xyz"})
        original = {"Content-Type": "application/json"}
        headers = auth.apply_to_headers(dict(original))
        assert headers == original

    def test_apply_preserves_existing_headers(self) -> None:
        """apply_to_headers merges into existing headers without removing them."""
        auth = AuthConfig(auth_type="bearer", config={"token": "tok"})
        headers = auth.apply_to_headers({"Content-Type": "application/json"})
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer tok"


class TestBuildAuth:
    """Tests for the build_auth factory function."""

    def test_build_auth_returns_auth_config(self) -> None:
        """build_auth returns an AuthConfig for a valid auth_type."""
        auth = build_auth("bearer", {"token": "abc"})
        assert auth is not None
        assert auth.auth_type == "bearer"
        assert auth.config == {"token": "abc"}

    def test_build_auth_returns_none_for_none_type(self) -> None:
        """build_auth returns None when auth_type is None."""
        auth = build_auth(None, {})
        assert auth is None

    def test_build_auth_returns_none_for_empty_type(self) -> None:
        """build_auth returns None when auth_type is an empty string."""
        auth = build_auth("", {})
        assert auth is None

    def test_build_auth_passes_config_through(self) -> None:
        """build_auth forwards the config dict to AuthConfig unchanged."""
        config = {"username": "u", "password": "p", "extra": "data"}
        auth = build_auth("basic", config)
        assert auth.config is config

    def test_build_auth_basic_type(self) -> None:
        """build_auth with 'basic' produces a usable AuthConfig."""
        auth = build_auth("basic", {"username": "user", "password": "pass"})
        headers = auth.apply_to_headers({})
        expected = base64.b64encode(b"user:pass").decode()
        assert headers["Authorization"] == f"Basic {expected}"

    def test_build_auth_api_key_type(self) -> None:
        """build_auth with 'api_key' produces a usable AuthConfig."""
        auth = build_auth("api_key", {"key": "mykey", "header_name": "X-Key"})
        headers = auth.apply_to_headers({})
        assert headers["X-Key"] == "mykey"
