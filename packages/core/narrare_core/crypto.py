"""Fernet encryption helper for API keys.

Provides symmetric encryption/decryption for sensitive data (API keys)
stored in the database. Uses the ``cryptography`` library's Fernet
scheme which guarantees that a message encrypted cannot be manipulated
or read without the key.

The encryption key MUST be provided via the ``NARRARE_ENCRYPTION_KEY``
environment variable. If it is missing, every encrypt/decrypt call
raises ``ConfigurationError``.

Usage::

    from narrare_core.crypto import encrypt, decrypt

    ciphertext = encrypt("sk-ant-api03-...")
    plaintext  = decrypt(ciphertext)

See: openspec/changes/configurable-model-routing/design.md (D6)
"""

from __future__ import annotations

from cryptography.fernet import Fernet

from narrare_core.settings import get_core_settings
from narrare_core.shared.errors import ConfigurationError


def _get_key() -> bytes:
    """Retrieve the Fernet encryption key from the environment.

    Returns:
        The raw bytes of the base64-encoded Fernet key.

    Raises:
        ConfigurationError: If ``NARRARE_ENCRYPTION_KEY`` is not set.
    """
    key = get_core_settings().encryption_key
    if not key:
        raise ConfigurationError(
            "NARRARE_ENCRYPTION_KEY environment variable is not set. "
            "Generate one with: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"',
            code="MISSING_ENCRYPTION_KEY",
        )
    return key.encode()


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string using Fernet.

    Args:
        plaintext: The secret to encrypt (e.g. an API key).

    Returns:
        The Fernet-encrypted token as a string (safe for DB storage).

    Raises:
        ConfigurationError: If ``NARRARE_ENCRYPTION_KEY`` is missing.
    """
    return Fernet(_get_key()).encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a Fernet-encrypted token.

    Args:
        token: The encrypted token previously produced by :func:`encrypt`.

    Returns:
        The original plaintext string.

    Raises:
        ConfigurationError: If ``NARRARE_ENCRYPTION_KEY`` is missing.
        cryptography.fernet.InvalidToken: If the token is corrupted or
            was encrypted with a different key.
    """
    return Fernet(_get_key()).decrypt(token.encode()).decode()
