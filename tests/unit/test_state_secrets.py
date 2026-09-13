"""Backend selection is deliberately fail-closed (J2): a machine with neither the OS
keyring nor `cryptography` installed must refuse to store a secret, never fall back to
something weaker. `keyring` and `cryptography` are both optional extras, so CI's default
install genuinely lacks one or the other on any given platform -- these tests simulate
every combination rather than depending on which extras happen to be installed here.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from sclpl.state import secrets as store


def _block_import(monkeypatch: pytest.MonkeyPatch, *module_names: str) -> None:
    """Make `import <name>` raise ImportError, regardless of what is actually installed."""
    for name in module_names:
        monkeypatch.setitem(sys.modules, name, None)


def _fake_working_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    class _WorkingBackend:
        pass

    fake_keyring = SimpleNamespace(
        get_keyring=lambda: _WorkingBackend(),
        set_password=lambda service, key, value: None,
    )
    fake_fail_module = SimpleNamespace(Keyring=type("Keyring", (), {}))
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    monkeypatch.setitem(sys.modules, "keyring.backends", SimpleNamespace(fail=fake_fail_module))
    monkeypatch.setitem(sys.modules, "keyring.backends.fail", fake_fail_module)


def _fake_unusable_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    """`keyring` is installed, but there is no daemon: it falls back to `fail.Keyring`."""

    class _FailBackend:
        pass

    fake_keyring = SimpleNamespace(get_keyring=lambda: _FailBackend())
    fake_fail_module = SimpleNamespace(Keyring=_FailBackend)
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    monkeypatch.setitem(sys.modules, "keyring.backends", SimpleNamespace(fail=fake_fail_module))
    monkeypatch.setitem(sys.modules, "keyring.backends.fail", fake_fail_module)


def test_keyring_is_used_when_installed_and_working(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_working_keyring(monkeypatch)
    result = store.backend()
    assert result.name == "keyring"


def test_keyring_installed_but_unusable_is_treated_as_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A keyring with no daemon (headless CI) must not raise -- it falls through."""
    _fake_unusable_keyring(monkeypatch)
    monkeypatch.setenv("SCLPL_HOME", str(tmp_path))
    result = store.backend()
    assert result.name != "keyring"


def _fake_fernet(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stand-in for `cryptography.fernet.Fernet`, present regardless of whether the
    real `cryptography` package happens to be installed in the ambient environment."""
    fake_fernet_module = SimpleNamespace(Fernet=object())
    monkeypatch.setitem(sys.modules, "cryptography", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "cryptography.fernet", fake_fernet_module)


def test_falls_back_to_encrypted_file_without_a_keyring(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _block_import(monkeypatch, "keyring", "keyring.backends", "keyring.backends.fail")
    _fake_fernet(monkeypatch)
    monkeypatch.setenv("SCLPL_HOME", str(tmp_path))
    result = store.backend()
    assert result.name == "encrypted-file"


def test_refuses_rather_than_storing_somewhere_weak(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Neither backend available: `backend()` reports "none", and `put()` is fatal."""
    _block_import(
        monkeypatch,
        "keyring",
        "keyring.backends",
        "keyring.backends.fail",
        "cryptography",
        "cryptography.fernet",
    )
    monkeypatch.setenv("SCLPL_HOME", str(tmp_path))

    result = store.backend()
    assert result.name == "none"

    with pytest.raises(store.NoSecureStorage) as excinfo:
        store.put("demo", "hunter2")
    assert "keyring" in str(excinfo.value)
    assert "crypto" in str(excinfo.value)
