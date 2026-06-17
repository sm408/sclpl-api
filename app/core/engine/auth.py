from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AuthConfig:
    auth_type: str
    config: dict[str, Any]

    def apply_to_headers(self, headers: dict[str, str]) -> dict[str, str]:
        if self.auth_type == "bearer":
            token = self.config.get("token", "")
            headers["Authorization"] = f"Bearer {token}"
        elif self.auth_type == "basic":
            import base64

            user = self.config.get("username", "")
            password = self.config.get("password", "")
            encoded = base64.b64encode(f"{user}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
        elif self.auth_type == "api_key":
            key = self.config.get("key", "")
            header_name = self.config.get("header_name", "X-API-Key")
            headers[header_name] = key
        return headers


def build_auth(request_auth_type: str | None, request_auth_config: dict[str, Any]) -> AuthConfig | None:
    if not request_auth_type:
        return None
    return AuthConfig(auth_type=request_auth_type, config=request_auth_config)
