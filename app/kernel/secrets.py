"""Two tiers of API-key storage: the OS keychain first, Fernet as the fallback.

``save_key`` returns exactly what the profile's ``api_key`` column holds: an
empty string in the keyring tier (the plaintext lives in the OS keychain
under this app's service name and the profile id) or Fernet ciphertext in the
Fernet tier (whose key is the ``NARRE_SECRET_KEY`` environment variable).
With neither a usable keychain nor ``NARRE_SECRET_KEY``, storing is refused
by name — there is no silent third tier and no auto-generated key file. A
key its tier can no longer produce — a restored database whose keychain was
cleared, a rotated ``NARRE_SECRET_KEY`` — fails ``load_key`` with
``KeyUnavailableError``, whose message names the profile id and never the key.

The module never touches the database: the caller (the settings service)
writes ``api_key`` with the returned column value and ``api_key_hint`` with
the last four characters — a hint, not a secret. ``NARRE_KEYRING=off`` forces
the Fernet tier, so tests and the E2E stack never touch a developer's real
keychain.
"""

from contextlib import suppress
from os import environ
from uuid import UUID  # noqa: TC003

import keyring
from cryptography.fernet import Fernet, InvalidToken
from keyring.backends.null import Keyring as NullKeyring
from keyring.errors import PasswordDeleteError

SERVICE = "narrare"
"""The keyring service name; the entry's username is the profile id."""

_PROBE = "__narrare_tier_probe__"
"""A username no profile has: reading it only asks the backend to answer."""


class NoKeyStoreError(RuntimeError):
    """Neither a usable OS keychain nor ``NARRE_SECRET_KEY``: storing is refused.

    No auto-generated key file exists below the two tiers (design D3), so the
    caller cannot store an ``api_key`` at all until one of them is configured.
    """


class KeyUnavailableError(RuntimeError):
    """The stored key cannot be produced again: gone from the keychain, or
    undecryptable ciphertext. The message names the profile id — and never the
    key — so a caller can say which configuration lost its key while the
    masked list keeps showing the hint.
    """


def _keyring_usable() -> bool:
    """Whether the OS keychain can really hold entries for this process.

    ``NARRE_KEYRING=off`` forces the Fernet tier (the knob tests use). A
    fail or vault backend raises on every operation, and the null backend
    accepts writes that go nowhere — either way a saved key would be silently
    lost, so neither counts as a keychain.
    """
    if environ.get("NARRE_KEYRING", "").strip().lower() == "off":
        return False
    backend = keyring.get_keyring()
    if isinstance(backend, NullKeyring):
        return False
    try:
        backend.get_password(SERVICE, _PROBE)
    except Exception:
        # The backend announced itself but cannot answer (fail, vault, or a
        # keychain this process may not reach): not a place to store a key.
        return False
    return True


def _fernet() -> Fernet | None:
    """The Fernet tier's cipher, or ``None`` when ``NARRE_SECRET_KEY`` is unset."""
    secret = environ.get("NARRE_SECRET_KEY")
    if not secret:
        return None
    return Fernet(secret.encode())


def save_key(profile_id: UUID, plaintext: str) -> str:
    """Store the key in the best available tier and name what it returned.

    The return value is what the ``api_key`` column holds: ``""`` when the
    keychain took the plaintext, Fernet ciphertext otherwise. Raises
    :class:`NoKeyStoreError` when no tier can store a key.
    """
    if _keyring_usable():
        keyring.set_password(SERVICE, str(profile_id), plaintext)
        return ""
    fernet = _fernet()
    if fernet is None:
        raise NoKeyStoreError(
            "no OS keychain is available and NARRE_SECRET_KEY is not set; "
            "an API key cannot be stored"
        )
    return fernet.encrypt(plaintext.encode()).decode()


def load_key(profile_id: UUID, column: str) -> str:
    """Produce the plaintext again from whichever tier stored it.

    ``column`` is the profile's ``api_key`` value, which names its tier: empty
    means the keychain holds the key, anything else is ciphertext to decrypt.
    Raises :class:`KeyUnavailableError` — the message names the profile id —
    when the tier cannot produce the key.
    """
    entry = str(profile_id)
    if not column:
        stored: str | None = None
        if _keyring_usable():
            with suppress(Exception):
                stored = keyring.get_password(SERVICE, entry)
        if stored is not None:
            return stored
        raise KeyUnavailableError(f"the keychain no longer holds the key of profile {entry}")
    fernet = _fernet()
    if fernet is None:
        raise KeyUnavailableError(
            f"cannot decrypt the stored key of profile {entry}: NARRE_SECRET_KEY is not set"
        )
    try:
        return fernet.decrypt(column.encode()).decode()
    except InvalidToken:
        raise KeyUnavailableError(f"cannot decrypt the stored key of profile {entry}") from None


def erase_key(profile_id: UUID) -> None:
    """Remove the keychain entry this profile's key lives in, if any.

    The Fernet tier has no keychain entry (the ciphertext sits in the column,
    which the caller deletes with the row), and a missing entry is not an
    error: erasing a profile that never stored a key stays quiet.
    """
    if not _keyring_usable():
        return
    with suppress(PasswordDeleteError, KeyError):
        keyring.delete_password(SERVICE, str(profile_id))
