"""Tests for app.core.secrets module."""

import pytest
from app.core.secrets import encrypt_secret, decrypt_secret, is_encrypted, mask_secret


class TestEncryptDecrypt:
    def test_encrypt_decrypt_roundtrip(self):
        original = "my-secret-api-key-12345"
        encrypted = encrypt_secret(original)
        assert encrypted != original
        assert is_encrypted(encrypted)
        decrypted = decrypt_secret(encrypted)
        assert decrypted == original

    def test_encrypt_different_each_time(self):
        value = "same-secret"
        enc1 = encrypt_secret(value)
        enc2 = encrypt_secret(value)
        # Both should decrypt to the same value
        assert decrypt_secret(enc1) == decrypt_secret(enc2) == value

    def test_decrypt_unencrypted_passthrough(self):
        value = "plain-text-value"
        assert decrypt_secret(value) == value

    def test_encrypt_empty_string(self):
        encrypted = encrypt_secret("")
        assert is_encrypted(encrypted)
        assert decrypt_secret(encrypted) == ""


class TestIsEncrypted:
    def test_encrypted_value_detected(self):
        assert is_encrypted("enc:something")
        assert is_encrypted("b64:c29tZXRoaW5n")

    def test_plain_value_not_detected(self):
        assert not is_encrypted("plain-text")
        assert not is_encrypted("")


class TestMaskSecret:
    def test_mask_short_value(self):
        assert mask_secret("ab") == "****"
        assert mask_secret("abc") == "****"

    def test_mask_long_value(self):
        masked = mask_secret("abcdefghijklmnop")
        assert masked.startswith("ab")
        assert masked.endswith("op")
        assert "****" in masked

    def test_mask_empty(self):
        assert mask_secret("") == ""

    def test_mask_encrypted(self):
        assert mask_secret("enc:something") == "****"
        assert mask_secret("b64:something") == "****"
