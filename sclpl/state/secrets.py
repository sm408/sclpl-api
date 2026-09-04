"""Credentials, stored somewhere that is actually a secret.

This closes defect 4. The engine this replaces fell back to **base64** when a keyring was
unavailable, and said nothing. Base64 is not encryption; it is an encoding a person can
undo in their head. A user who believed their token was protected had it stored in plain
sight, and nothing told them.

Three backends, tried in order:

1. **The OS keyring** -- Keychain, Credential Manager, Secret Service. The right answer,
   because it is already the thing the user's other tools use and it is already unlocked
   when they are logged in.
2. **An encrypted file** -- Fernet, with the key at `0600`. For a server with no
   keyring daemon, which is a real situation and not a mistake.
3. **Nothing.** Refuse, and say which of the two to install.

**There is no fourth.** Refusing is the whole point. A fallback weaker than what the user
asked for, applied without telling them, is worse than an error -- an error is visible
the first time, and a weak store is invisible until it matters.

Both optional backends are *extras*, so `pip install sclpl` stays small. The refusal
names the exact install command, because "no secure storage available" without one is a
dead end.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from sclpl.errors import ValidationError, did_you_mean

SERVICE = "sclpl"


def _home() -> Path:
    """Where the encrypted-file backend keeps its key and its store.

    Beside the config, not in the cache: a cache is something a user may delete to
    reclaim space, and deleting a key destroys every secret it protected.
    """
    override = os.environ.get("SCLPL_HOME")
    return Path(override) if override else Path.home() / ".sclpl"


@dataclass(frozen=True, slots=True)
class Backend:
    """Which store is in use, and why."""

    name: str
    detail: str = ""

    def describe(self) -> str:
        return f"{self.name}{f' ({self.detail})' if self.detail else ''}"


class NoSecureStorage(ValidationError):
    """Neither backend is available. Deliberately fatal."""

    def __init__(self) -> None:
        super().__init__(
            "no secure place to keep a secret is available",
            remedies=[
                "pip install 'sclpl[keyring]'   -- uses the OS keyring",
                "pip install 'sclpl[crypto]'    -- an encrypted file, for a server",
                "sclpl will not fall back to anything weaker, so nothing is stored",
            ],
        )


# -- backend detection --------------------------------------------------------------


def _keyring() -> object | None:
    """The `keyring` module, if it is installed *and* has a working backend.

    Installed is not the same as usable: `keyring` falls back to a `fail.Keyring` on a
    machine with no daemon, and that raises on the first `set_password`. Checking here
    means the encrypted-file backend gets its turn rather than the user getting an
    exception from inside somebody else's package.
    """
    try:
        import keyring
        from keyring.backends import fail
    except ImportError:
        return None
    try:
        if isinstance(keyring.get_keyring(), fail.Keyring):
            return None
    except Exception:  # noqa: BLE001 - an unusable keyring is not an error, it is a no
        return None
    return cast(object, keyring)


def _fernet() -> object | None:
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return None
    return Fernet


def backend() -> Backend:
    """Which store will be used. `sclpl doctor` prints this."""
    if _keyring() is not None:
        import keyring

        return Backend("keyring", type(keyring.get_keyring()).__name__)
    if _fernet() is not None:
        return Backend("encrypted-file", str(_store_path()))
    return Backend("none", "neither keyring nor cryptography is installed")


# -- the store ----------------------------------------------------------------------


def _store_path() -> Path:
    return _home() / "secrets.enc"


def _key_path() -> Path:
    return _home() / "secrets.key"


def _load_key() -> bytes:
    """The Fernet key, created at `0600` if it is not there.

    `0600` is not decoration. A key readable by every account on the machine protects
    nothing, so the file is created with the mode it needs rather than created and then
    fixed -- there is no window in which it is wrong.
    """
    path = _key_path()
    if path.exists():
        _refuse_if_readable(path)
        return path.read_bytes()

    from cryptography.fernet import Fernet

    key: bytes = Fernet.generate_key()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Opened with the mode set, rather than written and then chmod'd: between those two
    # calls the key would be world-readable.
    handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "wb") as file:
        file.write(key)
    return key


def _refuse_if_readable(path: Path) -> None:
    """A key anyone can read is not a key. Say so rather than using it anyway."""
    if os.name == "nt":
        # Windows permissions are ACLs, not mode bits; `st_mode` says nothing useful.
        return
    mode = path.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ValidationError(
            f"{path} is readable by other accounts",
            remedies=[f"chmod 600 {path}", "the key protects nothing while it is shared"],
        )


def _read_store() -> dict[str, str]:
    path = _store_path()
    if not path.exists():
        return {}
    from cryptography.fernet import Fernet, InvalidToken

    try:
        decrypted = Fernet(_load_key()).decrypt(path.read_bytes())
    except InvalidToken as error:
        raise ValidationError(
            f"{path} cannot be decrypted with {_key_path()}",
            remedies=[
                "the key was replaced or the file came from another machine",
                f"delete {path} to start again -- the secrets in it are unrecoverable",
            ],
        ) from error
    return dict(json.loads(decrypted))


def _write_store(values: dict[str, str]) -> None:
    from cryptography.fernet import Fernet

    payload = Fernet(_load_key()).encrypt(json.dumps(values).encode("utf-8"))
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "wb") as file:
        file.write(payload)


# -- the operations -----------------------------------------------------------------


def put(name: str, value: str, *, env: str = "default") -> Backend:
    """Store a secret. Raises rather than storing it somewhere weak."""
    key = _qualified(name, env)
    module = _keyring()
    if module is not None:
        import keyring

        keyring.set_password(SERVICE, key, value)
        return backend()

    if _fernet() is not None:
        values = _read_store()
        values[key] = value
        _write_store(values)
        return backend()

    raise NoSecureStorage()


def get(name: str, *, env: str = "default") -> str | None:
    """A secret, or None. Falls back to the environment, which is never *stored* by us.

    `SCLPL_SECRET_<NAME>` exists for CI, where there is no keyring and no interactive
    session to unlock one, and where the secret arrives as an environment variable
    anyway. Reading one is not the same as writing one somewhere weak.
    """
    key = _qualified(name, env)
    module = _keyring()
    if module is not None:
        import keyring

        found: str | None = keyring.get_password(SERVICE, key)
        if found is not None:
            return found

    if _fernet() is not None and _store_path().exists():
        stored = _read_store().get(key)
        if stored is not None:
            return stored

    return os.environ.get(f"SCLPL_SECRET_{name.upper().replace('-', '_')}")


def delete(name: str, *, env: str = "default") -> bool:
    """Forget a secret. False if there was nothing to forget."""
    key = _qualified(name, env)
    removed = False

    module = _keyring()
    if module is not None:
        import keyring

        if keyring.get_password(SERVICE, key) is not None:
            keyring.delete_password(SERVICE, key)
            removed = True

    if _fernet() is not None and _store_path().exists():
        values = _read_store()
        if values.pop(key, None) is not None:
            _write_store(values)
            removed = True
    return removed


def names(*, env: str = "default") -> list[str]:
    """What is stored, for this environment. **Names only, never values.**

    The keyring has no portable way to enumerate what a service holds, so this lists
    what the file backend knows about. A keyring-only setup returns nothing here, which
    is a limitation of the API rather than of the store -- `sclpl secret get` still
    works.
    """
    if _fernet() is None or not _store_path().exists():
        return []
    prefix = f"{env}/"
    return sorted(key[len(prefix) :] for key in _read_store() if key.startswith(prefix))


def resolve(names_wanted: list[str], *, env: str = "default") -> dict[str, str]:
    """Every named secret, or an error naming the ones that are missing.

    All of them at once, before the run starts. Discovering the third of four is missing
    after two requests have been paid for is the failure preflight exists to prevent.
    """
    found: dict[str, str] = {}
    missing: list[str] = []
    for name in names_wanted:
        value = get(name, env=env)
        if value is None:
            missing.append(name)
        else:
            found[name] = value

    if missing:
        available = names(env=env)
        remedies = []
        suggestion = did_you_mean(missing[0], available) if available else None
        if suggestion:
            remedies.append(suggestion)
        remedies.append(f"sclpl secret set {missing[0]}")
        remedies.append(f"or set SCLPL_SECRET_{missing[0].upper().replace('-', '_')}")
        raise ValidationError(
            f"no secret named {', '.join(repr(name) for name in missing)}",
            remedies=remedies,
        )
    return found


def _qualified(name: str, env: str) -> str:
    """`env/name`. Environments are namespaces, not separate stores.

    One store with prefixed keys rather than a store per environment: the keyring has
    one namespace per service anyway, and two stores would mean two things to unlock.
    """
    if "/" in name:
        raise ValidationError(
            f"a secret name cannot contain '/': {name!r}",
            remedies=["the environment is a separate argument: --env staging"],
        )
    return f"{env}/{name}"
