from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


@dataclass
class RequestParam:
    key: str
    value: str
    enabled: bool = True


@dataclass
class RequestDef:
    id: str
    name: str
    method: HttpMethod
    url: str
    headers: list[RequestParam] = field(default_factory=list)
    query_params: list[RequestParam] = field(default_factory=list)
    body: str | None = None
    body_type: str | None = None
    auth_type: str | None = None
    auth_config: dict[str, Any] = field(default_factory=dict)
    collection_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
