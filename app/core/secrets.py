"""Secrets encryption for SCLPLAPI environment variables.

Uses Fernet symmetric encryption from the cryptography library.
Falls back to base64 encoding if cryptography is not installed.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

_SECRETS_KEY_FILE = Path.home() / ".sclplapi" / ".secrets_key"


def _get_or_create_key() -> bytes:
    """Get or create the encryption key."""
    if _SECRETS_KEY_FILE.exists():
        return _SECRETS_KEY_FILE.read_bytes().strip()

    key = os.urandom(32)
    _SECRETS_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SECRETS_KEY_FILE.write_bytes(key)
    return key


def _get_fernet():
    """Get Fernet instance if cryptography is available."""
    try:
        from cryptography.fernet import Fernet
        key = _get_or_create_key()
        fernet_key = base64.urlsafe_b64encode(key[:32])
        return Fernet(fernet_key)
    except ImportError:
        return None


def encrypt_secret(value: str) -> str:
    """Encrypt a secret value.

    Uses Fernet if cryptography is available, otherwise base64 encodes.
    """
    fernet = _get_fernet()
    if fernet:
        encrypted = fernet.encrypt(value.encode("utf-8"))
        return f"enc:{encrypted.decode('utf-8')}"
    else:
        encoded = base64.b64encode(value.encode("utf-8")).decode("utf-8")
        return f"b64:{encoded}"


def decrypt_secret(encrypted_value: str) -> str:
    """Decrypt a secret value.

    Handles both Fernet-encrypted and base64-encoded values.
    Returns the original value if not encrypted.
    """
    if encrypted_value.startswith("enc:"):
        fernet = _get_fernet()
        if fernet:
            try:
                decrypted = fernet.decrypt(encrypted_value[4:].encode("utf-8"))
                return decrypted.decode("utf-8")
            except Exception:
                return encrypted_value
        return encrypted_value[4:]

    if encrypted_value.startswith("b64:"):
        try:
            decoded = base64.b64decode(encrypted_value[4:].encode("utf-8"))
            return decoded.decode("utf-8")
        except Exception:
            return encrypted_value

    return encrypted_value


def is_encrypted(value: str) -> bool:
    """Check if a value is encrypted."""
    return value.startswith("enc:") or value.startswith("b64:")


def mask_secret(value: str) -> str:
    """Mask a secret value for display."""
    if not value:
        return ""
    if is_encrypted(value):
        return "****"
    if len(value) <= 4:
        return "****"
    return value[:2] + "*" * (len(value) - 4) + value[-2:]
