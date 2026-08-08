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
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
import sqlalchemy
from cryptography.fernet import Fernet, InvalidToken

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncEngine

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


# ── Fixtures ────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="module", autouse=True, loop_scope="session")
async def _clean_user_providers(test_engine: AsyncEngine) -> AsyncGenerator[None]:  # pyright: ignore[reportUnusedFunction] — autouse fixture, invoked via decorator reflection.
    """Remove pre-existing ``user_providers``/``users`` rows before this module.

    ``rotate_keys`` iterates over *every* ``user_providers`` row (by design —
    production rotates the whole table).  Leftover rows committed by earlier
    sessions (dev seeding, manual script runs) are invisible to the per-test
    rollback isolation of ``db_session``, so absolute count assertions
    (``total_rows == 2`` etc.) and decryption with a freshly generated test
    key would fail with ``InvalidToken``.  Truncating once per module makes
    these tests self-contained; the per-test rollback still isolates the
    rows each test creates from its neighbours.

    This is DML cleanup on the test database only — no schema change, so
    RULE-14 (schema exclusively via Alembic migrations) stays intact.
    """
    async with test_engine.begin() as conn:
        await conn.execute(sqlalchemy.text("TRUNCATE user_providers, users CASCADE"))
    yield


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

        # Exactly 1 rotated (our anthropic row) and 1 skipped (our ollama
        # row). DB isolation guarantees no leaked rows from other tests.
        assert result.rotated == 1
        assert result.skipped == 1
        assert result.total_rows == 2
