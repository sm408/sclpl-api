from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CollectionItem:
    id: str
    name: str
    request_id: str | None = None
    folder_id: str | None = None


@dataclass
class Collection:
    id: str
    name: str
    description: str = ""
    items: list[CollectionItem] = field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
