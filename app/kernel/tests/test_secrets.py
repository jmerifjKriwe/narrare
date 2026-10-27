"""The key-storage tiers: OS keyring first, Fernet under NARRE_SECRET_KEY.

The boundaries the WP2a review pins at the unit level: what save_key returns
is exactly what the api_key column holds — "" in the keyring tier, ciphertext
in the Fernet tier, never the plaintext — and a key its tier can no longer
produce fails load_key with KeyUnavailableError naming the profile id, never
the key. No test touches a developer's real keychain: the keyring tier runs
on an in-memory backend installed per test, the Fernet tier on
NARRE_KEYRING=off.
"""

from collections.abc import Iterator  # noqa: TC003
from uuid import uuid4

import keyring
import pytest
from cryptography.fernet import Fernet
from keyring.backend import KeyringBackend
from keyring.compat import properties
from keyring.errors import PasswordDeleteError

from app.kernel import secrets

KEY = "sk-test-0123456789abcdefghijklmnop"
"""A full-length stand-in shaped like a vendor key; never a real one."""


class _MemoryKeyring(KeyringBackend):
    """A dict with the backend interface: the keyring tier without a keychain.

    delete_password mirrors the strict real backends (an absent entry
    raises), so erase_key's tolerance is exercised against the truth, not a
    stub's silence.
    """

    @properties.classproperty
    def priority(self) -> float:  # the receiver is the class, keyring's idiom
        return 1.0

    def __init__(self) -> None:
        self.entries: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, username: str, password: str) -> None:
        self.entries[(service, username)] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self.entries.get((service, username))

    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self.entries:
            raise PasswordDeleteError(f"no entry for {username} on {service}")
        del self.entries[(service, username)]


@pytest.fixture
def memory_keyring() -> Iterator[_MemoryKeyring]:
    """Install the in-memory backend for one test, then restore the real one."""
    original = keyring.get_keyring()
    backend = _MemoryKeyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(original)


def test_the_fernet_tier_round_trips_and_never_holds_the_plaintext(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the Fernet column carries ciphertext and gives the key back."""
    monkeypatch.setenv("NARRE_KEYRING", "off")
    monkeypatch.setenv("NARRE_SECRET_KEY", Fernet.generate_key().decode())
    profile_id = uuid4()

    column = secrets.save_key(profile_id, KEY)

    assert column  # ciphertext, not the keyring tier's empty column
    assert KEY not in column  # the storage boundary: never the plaintext
    assert secrets.load_key(profile_id, column) == KEY


def test_storing_without_any_tier_is_refused_by_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the named refusal when neither a keychain nor a secret key exists."""
    monkeypatch.setenv("NARRE_KEYRING", "off")
    monkeypatch.delenv("NARRE_SECRET_KEY", raising=False)

    with pytest.raises(secrets.NoKeyStoreError) as raised:
        secrets.save_key(uuid4(), KEY)

    assert "NARRE_SECRET_KEY" in str(raised.value)


def test_a_viable_keyring_wins_over_a_secret_key_and_keeps_the_column_empty(
    memory_keyring: _MemoryKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the OS keyring takes precedence and the column stays empty."""
    monkeypatch.setenv("NARRE_SECRET_KEY", Fernet.generate_key().decode())
    profile_id = uuid4()

    column = secrets.save_key(profile_id, KEY)

    assert column == ""  # the api_key column holds nothing in this tier
    assert memory_keyring.get_password(secrets.SERVICE, str(profile_id)) == KEY
    assert secrets.load_key(profile_id, column) == KEY


def test_a_key_the_keyring_lost_fails_by_name_not_by_key(
    memory_keyring: _MemoryKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a cleared keychain raises KeyUnavailableError naming the profile.

    The restored-database, cleared-keychain case: the caller's hint column
    still shows the mask, but only the keychain could produce the key.
    """
    monkeypatch.delenv("NARRE_SECRET_KEY", raising=False)
    profile_id = uuid4()
    secrets.save_key(profile_id, KEY)
    memory_keyring.entries.clear()  # the keychain lost the entry

    with pytest.raises(secrets.KeyUnavailableError) as raised:
        secrets.load_key(profile_id, "")

    assert str(profile_id) in str(raised.value)  # names the profile...
    assert KEY not in str(raised.value)  # ...and never the key


def test_ciphertext_a_rotated_secret_key_cannot_decrypt_fails_by_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify undecryptable ciphertext raises KeyUnavailableError naming the profile."""
    monkeypatch.setenv("NARRE_KEYRING", "off")
    monkeypatch.setenv("NARRE_SECRET_KEY", Fernet.generate_key().decode())
    profile_id = uuid4()
    column = secrets.save_key(profile_id, KEY)
    monkeypatch.setenv("NARRE_SECRET_KEY", Fernet.generate_key().decode())  # rotated away

    with pytest.raises(secrets.KeyUnavailableError) as raised:
        secrets.load_key(profile_id, column)

    assert str(profile_id) in str(raised.value)
    assert KEY not in str(raised.value)


def test_ciphertext_without_a_secret_key_fails_by_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify ciphertext nobody can decrypt raises the same named error."""
    monkeypatch.setenv("NARRE_KEYRING", "off")
    monkeypatch.setenv("NARRE_SECRET_KEY", Fernet.generate_key().decode())
    profile_id = uuid4()
    column = secrets.save_key(profile_id, KEY)
    monkeypatch.delenv("NARRE_SECRET_KEY", raising=False)

    with pytest.raises(secrets.KeyUnavailableError) as raised:
        secrets.load_key(profile_id, column)

    assert str(profile_id) in str(raised.value)


def test_erasing_removes_the_keyring_entry_and_tolerates_a_missing_one(
    memory_keyring: _MemoryKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify erase_key clears the keychain entry and stays quiet when none exists."""
    monkeypatch.delenv("NARRE_SECRET_KEY", raising=False)
    profile_id = uuid4()
    secrets.save_key(profile_id, KEY)

    secrets.erase_key(profile_id)

    assert memory_keyring.get_password(secrets.SERVICE, str(profile_id)) is None
    secrets.erase_key(profile_id)  # nothing left: quiet, not an error


def test_erasing_in_the_fernet_tier_has_nothing_to_touch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify erase stays quiet in the Fernet tier, where no keychain entry exists."""
    monkeypatch.setenv("NARRE_KEYRING", "off")
    monkeypatch.setenv("NARRE_SECRET_KEY", Fernet.generate_key().decode())
    secrets.save_key(uuid4(), KEY)

    secrets.erase_key(uuid4())  # the ciphertext lives in the column, not here
