"""Tests for core/crypto.py — Fernet encryption helpers."""

from __future__ import annotations

import pytest

from narrare_core.crypto import decrypt, encrypt
from narrare_core.settings import get_core_settings
from narrare_core.shared.errors import ConfigurationError


class TestEncryptionRoundTrip:
    def test_encrypt_then_decrypt_returns_original(self) -> None:
        """Round-trip: encrypt(plaintext) → decrypt(ciphertext) → plaintext."""
        plaintext = "sk-ant-api03-abc123def456"
        ciphertext = encrypt(plaintext)
        assert decrypt(ciphertext) == plaintext

    def test_different_inputs_produce_different_ciphertexts(self) -> None:
        """Two different plaintexts must not produce the same ciphertext."""
        ct1 = encrypt("key-aaa")
        ct2 = encrypt("key-bbb")
        assert ct1 != ct2

    def test_same_input_produces_different_ciphertexts(self) -> None:
        """Fernet includes a timestamp, so same input → different ciphertext."""
        ct1 = encrypt("same-key")
        ct2 = encrypt("same-key")
        assert ct1 != ct2  # Different IV/timestamp each time

    def test_ciphertext_is_not_plaintext(self) -> None:
        """Encrypted output must not contain the original plaintext."""
        plaintext = "sk-secret-key-12345"
        ciphertext = encrypt(plaintext)
        assert plaintext not in ciphertext

    def test_empty_string_round_trip(self) -> None:
        """Edge case: encrypting/decrypting empty string."""
        ciphertext = encrypt("")
        assert decrypt(ciphertext) == ""

    def test_long_key_round_trip(self) -> None:
        """Edge case: very long API key."""
        long_key = "x" * 10000
        ciphertext = encrypt(long_key)
        assert decrypt(ciphertext) == long_key


class TestMissingEncryptionKey:
    def test_missing_encryption_key_raises_configuration_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NARRARE_ENCRYPTION_KEY not set → ConfigurationError."""
        monkeypatch.delenv("NARRARE_ENCRYPTION_KEY", raising=False)

        with pytest.raises(ConfigurationError, match="NARRARE_ENCRYPTION_KEY"):
            encrypt("test-key")

    def test_missing_key_on_decrypt_raises_configuration_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Decrypt with missing key → ConfigurationError."""
        # Encrypt with a valid key
        ciphertext = encrypt("test-key")

        # Now remove the key
        monkeypatch.delenv("NARRARE_ENCRYPTION_KEY", raising=False)
        # Clear the cached CoreSettings so decrypt re-reads the now-absent key
        get_core_settings.cache_clear()

        with pytest.raises(ConfigurationError, match="NARRARE_ENCRYPTION_KEY"):
            decrypt(ciphertext)

    def test_empty_encryption_key_raises_configuration_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Empty NARRARE_ENCRYPTION_KEY → ConfigurationError."""
        monkeypatch.setenv("NARRARE_ENCRYPTION_KEY", "")

        with pytest.raises(ConfigurationError, match="NARRARE_ENCRYPTION_KEY"):
            encrypt("test-key")
