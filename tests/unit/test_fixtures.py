"""Fixture bodies are verified and credentials never reach metadata."""

from __future__ import annotations

from pathlib import Path

import pytest

from sclpl.errors import ValidationError
from sclpl.run.fixtures import Fixture, Store


def test_record_and_replay_keeps_occurrences_separate(tmp_path: Path) -> None:
    store = Store(tmp_path)
    store.record(Fixture("GET", "https://example.test/orders", 0, 200, {"ETag": "a"}, b"one"))
    store.record(Fixture("GET", "https://example.test/orders", 1, 200, {}, b"two"))
    assert store.replay("GET", "https://example.test/orders", occurrence=1).body == b"two"


def test_fixture_metadata_redacts_auth_and_verifies_blob(tmp_path: Path) -> None:
    store = Store(tmp_path)
    path = store.record(
        Fixture("GET", "https://example.test", 0, 200, {"Authorization": "secret"}, b"ok")
    )
    assert "secret" not in path.read_text(encoding="utf-8")
    next(store.blobs.iterdir()).write_bytes(b"changed")
    with pytest.raises(ValidationError, match="digest mismatch"):
        store.replay("GET", "https://example.test")


def test_replay_reports_unused_recorded_requests(tmp_path: Path) -> None:
    store = Store(tmp_path)
    store.record(Fixture("GET", "https://example.test/one", 0, 200, {}, b"one"))
    store.record(Fixture("GET", "https://example.test/two", 0, 200, {}, b"two"))
    store.replay("GET", "https://example.test/one")
    assert len(store.unused()) == 1
