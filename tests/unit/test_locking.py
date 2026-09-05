"""Project mutation locks serialize writers and identify an owner on timeout."""

from __future__ import annotations

from pathlib import Path

import pytest

from sclpl.errors import ValidationError
from sclpl.state.locking import Lock


def test_lock_times_out_with_owner_details(tmp_path: Path) -> None:
    path = tmp_path / "mutation.lock"
    with Lock(path), pytest.raises(ValidationError, match="current owner: pid="):
        _acquire_immediately(path)


def _acquire_immediately(path: Path) -> None:
    with Lock(path, timeout=0):
        pass
