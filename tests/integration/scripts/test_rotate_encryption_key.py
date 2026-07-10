"""Integration tests for scripts/rotate_encryption_key.py — rotate_keys.

Uses a real PostgreSQL database (via the ``db_session`` fixture from
``tests/integration/conftest.py``).  Each test runs inside a transaction
that is rolled back on teardown, so no data persists between tests.
"""

from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.fernet import Fernet, InvalidToken

# Ensure scripts/ is importable (project root on sys.path).
_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.rotate_encryption_key import rotate_keys  # noqa: E402

from narrare.auth.models import User  # noqa: E402
from narrare.settings.models import UserProvider  # noqa: E402

# ── Helpers ──────────────────────────────────────────────────────


def _generate_key() -> str:
    """Generate a random Fernet key as a string."""
    return Fernet.generate_key().decode()


def _encrypt(key: str, plaintext: str) -> str:
    """Encrypt *plaintext* with *key* and return the token string."""
    return Fernet(key.encode()).encrypt(plaintext.encode()).decode()


async def _create_user(db_session: object) -> User:
    """Insert a test user and flush so the FK is satisfiable."""
    user = User(
        id=uuid.uuid4(),
        email=f"rottest-{uuid.uuid4().hex[:12]}@example.com",
        hashed_password="not-a-real-hash",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(user)  # type: ignore[attr-defined]
    await db_session.flush()  # type: ignore[attr-defined]
    return user


async def _create_provider(
    db_session: object,
    user: User,
    api_key_encrypted: str,
    provider_name: str = "anthropic",
) -> UserProvider:
    """Insert a UserProvider row and flush."""
    provider = UserProvider(
        id=uuid.uuid4(),
        user_id=user.id,
        provider_name=provider_name,
        api_key_encrypted=api_key_encrypted,
        is_active=True,
    )
    db_session.add(provider)  # type: ignore[attr-defined]
    await db_session.flush()  # type: ignore[attr-defined]
    return provider


# ── Tests ────────────────────────────────────────────────────────


class TestRotateKeysIntegration:
    """Integration tests with a real PostgreSQL database."""

    async def test_rotation_re_encrypts_with_new_key(self, db_session: object) -> None:
        """After rotation, the row decrypts with the new key, not the old."""
        old_key = _generate_key()
        new_key = _generate_key()

        user = await _create_user(db_session)
        provider = await _create_provider(
            db_session, user, _encrypt(old_key, "sk-integration-real")
        )

        result = await rotate_keys(old_key, new_key, db_session)

        assert result.rotated == 1
        assert result.skipped == 0
        assert result.total_rows >= 1

        # New key decrypts to the original plaintext
        decrypted = Fernet(new_key.encode()).decrypt(provider.api_key_encrypted.encode()).decode()
        assert decrypted == "sk-integration-real"

        # Old key can no longer decrypt
        with pytest.raises(InvalidToken):
            Fernet(old_key.encode()).decrypt(provider.api_key_encrypted.encode())

    async def test_wrong_old_key_raises_and_data_unchanged(self, db_session: object) -> None:
        """Wrong old key raises InvalidToken; the row is not modified."""
        old_key = _generate_key()
        wrong_key = _generate_key()
        new_key = _generate_key()

        user = await _create_user(db_session)
        provider = await _create_provider(
            db_session, user, _encrypt(old_key, "sk-should-not-change")
        )

        original_encrypted = provider.api_key_encrypted

        with pytest.raises(InvalidToken):
            await rotate_keys(wrong_key, new_key, db_session)

        # Row was not modified — decrypt still fails with wrong key but
        # succeeds with the original key.
        assert provider.api_key_encrypted == original_encrypted
        assert (
            Fernet(old_key.encode()).decrypt(provider.api_key_encrypted.encode()).decode()
            == "sk-should-not-change"
        )

    async def test_dry_run_does_not_modify_data(self, db_session: object) -> None:
        """Dry run reports counts but leaves api_key_encrypted unchanged."""
        old_key = _generate_key()
        new_key = _generate_key()

        user = await _create_user(db_session)
        provider = await _create_provider(db_session, user, _encrypt(old_key, "sk-dry-run-test"))

        original_encrypted = provider.api_key_encrypted

        result = await rotate_keys(old_key, new_key, db_session, dry_run=True)

        assert result.dry_run is True
        assert result.rotated == 1

        # Value unchanged — still decrypts with old key
        assert provider.api_key_encrypted == original_encrypted
        assert (
            Fernet(old_key.encode()).decrypt(provider.api_key_encrypted.encode()).decode()
            == "sk-dry-run-test"
        )

    async def test_empty_key_rows_are_skipped(self, db_session: object) -> None:
        """Ollama providers with empty api_key_encrypted are skipped."""
        old_key = _generate_key()
        new_key = _generate_key()

        user = await _create_user(db_session)
        await _create_provider(
            db_session,
            user,
            _encrypt(old_key, "sk-has-key"),
            provider_name="anthropic",
        )
        await _create_provider(db_session, user, "", provider_name="ollama")

        result = await rotate_keys(old_key, new_key, db_session)

        # At least 1 rotated (our anthropic row), at least 1 skipped (our ollama row).
        # Other rows from prior tests are rolled back, so counts should be exact.
        assert result.rotated >= 1
        assert result.skipped >= 1
        assert result.total_rows == result.rotated + result.skipped
