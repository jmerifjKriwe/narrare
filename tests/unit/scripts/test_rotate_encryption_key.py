"""Unit tests for scripts/rotate_encryption_key.py — rotate_keys function.

Tests the core rotation logic with a mock AsyncSession.  No database
required — these run in <1s as part of ``just test-unit``.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet, InvalidToken

# Ensure scripts/ is importable (project root on sys.path).
_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.rotate_encryption_key import rotate_keys  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Sequence


# ── Helpers ──────────────────────────────────────────────────────


def _generate_key() -> str:
    """Generate a random Fernet key as a string."""
    return Fernet.generate_key().decode()


def _encrypt(key: str, plaintext: str) -> str:
    """Encrypt *plaintext* with *key* and return the token string."""
    return Fernet(key.encode()).encrypt(plaintext.encode()).decode()


def _make_row(
    api_key_encrypted: str = "",
    provider_name: str = "anthropic",
) -> SimpleNamespace:
    """Create a lightweight row object mimicking UserProvider.

    Uses SimpleNamespace instead of the real SQLAlchemy model so the
    unit test has zero DB/ORM dependencies.
    """
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        provider_name=provider_name,
        api_key_encrypted=api_key_encrypted,
    )


class _FakeScalarResult:
    """Fake SQLAlchemy ScalarResult — returns pre-seeded rows."""

    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    def all(self) -> list[SimpleNamespace]:
        return self._rows


class _FakeResult:
    """Fake SQLAlchemy Result — scalars() returns a _FakeScalarResult."""

    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._scalars = _FakeScalarResult(rows)

    def scalars(self) -> _FakeScalarResult:
        return self._scalars


def _make_mock_session(rows: Sequence[SimpleNamespace]) -> AsyncMock:
    """Create a mock AsyncSession whose execute() returns *rows*.

    Uses an ``AsyncMock`` for the session (infrastructure, not domain
    logic) and Fake classes for the SQLAlchemy result chain, per ADR-030.
    """
    session = AsyncMock()
    session.execute.return_value = _FakeResult(list(rows))
    return session


# ── Tests ────────────────────────────────────────────────────────


class TestRotateKeysHappyPath:
    """Happy-path scenarios."""

    async def test_two_keys_one_empty_rotates_two_skips_one(self) -> None:
        """3 rows: 2 with encrypted keys, 1 empty (Ollama) → 2 rotated, 1 skipped."""
        old_key = _generate_key()
        new_key = _generate_key()

        rows = [
            _make_row(_encrypt(old_key, "sk-ant-001"), provider_name="anthropic"),
            _make_row(_encrypt(old_key, "sk-openai-002"), provider_name="openai"),
            _make_row("", provider_name="ollama"),
        ]
        session = _make_mock_session(rows)

        result = await rotate_keys(old_key, new_key, session)

        assert result.total_rows == 3
        assert result.rotated == 2
        assert result.skipped == 1
        assert result.dry_run is False

    async def test_re_encrypted_values_decrypt_with_new_key(self) -> None:
        """Re-encrypted values must decrypt with the new key, not the old one."""
        old_key = _generate_key()
        new_key = _generate_key()

        rows = [
            _make_row(_encrypt(old_key, "sk-secret-aaa"), provider_name="anthropic"),
            _make_row(_encrypt(old_key, "sk-secret-bbb"), provider_name="openai"),
        ]
        session = _make_mock_session(rows)

        await rotate_keys(old_key, new_key, session)

        # New key decrypts successfully
        assert (
            Fernet(new_key.encode()).decrypt(rows[0].api_key_encrypted.encode()).decode()
            == "sk-secret-aaa"
        )
        assert (
            Fernet(new_key.encode()).decrypt(rows[1].api_key_encrypted.encode()).decode()
            == "sk-secret-bbb"
        )

        # Old key can no longer decrypt (values were re-encrypted)
        with pytest.raises(InvalidToken):
            Fernet(old_key.encode()).decrypt(rows[0].api_key_encrypted.encode())
        with pytest.raises(InvalidToken):
            Fernet(old_key.encode()).decrypt(rows[1].api_key_encrypted.encode())

    async def test_sample_provider_names_populated(self) -> None:
        """Result includes provider names from rotated rows (for dry-run reporting)."""
        old_key = _generate_key()
        new_key = _generate_key()

        rows = [
            _make_row(_encrypt(old_key, "key-1"), provider_name="anthropic"),
            _make_row(_encrypt(old_key, "key-2"), provider_name="openai"),
        ]
        session = _make_mock_session(rows)

        result = await rotate_keys(old_key, new_key, session)

        assert set(result.sample_provider_names) == {"anthropic", "openai"}


class TestRotateKeysDryRun:
    """Dry-run mode: count but do not modify."""

    async def test_dry_run_does_not_modify_rows(self) -> None:
        """Dry run must not change any api_key_encrypted value."""
        old_key = _generate_key()
        new_key = _generate_key()

        rows = [
            _make_row(_encrypt(old_key, "sk-keep-me"), provider_name="anthropic"),
            _make_row("", provider_name="ollama"),
        ]
        session = _make_mock_session(rows)

        original_encrypted = rows[0].api_key_encrypted

        result = await rotate_keys(old_key, new_key, session, dry_run=True)

        assert result.dry_run is True
        assert result.rotated == 1
        assert result.skipped == 1
        # Value unchanged
        assert rows[0].api_key_encrypted == original_encrypted

    async def test_dry_run_result_flag_is_true(self) -> None:
        """Dry-run result must have dry_run=True."""
        old_key = _generate_key()
        new_key = _generate_key()

        rows = [_make_row(_encrypt(old_key, "sk-1"))]
        session = _make_mock_session(rows)

        result = await rotate_keys(old_key, new_key, session, dry_run=True)

        assert result.dry_run is True


class TestRotateKeysDecryptFailure:
    """Decrypt failure: wrong old key → error, no partial updates."""

    async def test_wrong_old_key_raises_invalid_token(self) -> None:
        """A wrong old key causes InvalidToken on the first non-empty row."""
        old_key = _generate_key()
        wrong_key = _generate_key()
        new_key = _generate_key()

        rows = [
            _make_row(_encrypt(old_key, "sk-real-key"), provider_name="anthropic"),
            _make_row("", provider_name="ollama"),
        ]
        session = _make_mock_session(rows)

        with pytest.raises(InvalidToken):
            await rotate_keys(wrong_key, new_key, session)

    async def test_wrong_old_key_no_partial_updates(self) -> None:
        """When the old key is wrong, no rows are modified (first decrypt fails)."""
        old_key = _generate_key()
        wrong_key = _generate_key()
        new_key = _generate_key()

        rows = [
            _make_row(_encrypt(old_key, "sk-aaa"), provider_name="anthropic"),
            _make_row(_encrypt(old_key, "sk-bbb"), provider_name="openai"),
            _make_row("", provider_name="ollama"),
        ]
        session = _make_mock_session(rows)

        original_values = [r.api_key_encrypted for r in rows]

        with pytest.raises(InvalidToken):
            await rotate_keys(wrong_key, new_key, session)

        # No row was modified — all values unchanged
        for row, original in zip(rows, original_values, strict=True):
            assert row.api_key_encrypted == original

    async def test_invalid_old_key_format_raises_value_error(self) -> None:
        """A malformed old key raises ValueError before any DB access."""
        new_key = _generate_key()

        rows = [_make_row(_encrypt(_generate_key(), "sk-1"))]
        session = _make_mock_session(rows)

        with pytest.raises(ValueError):
            await rotate_keys("not-a-valid-fernet-key", new_key, session)


class TestRotateKeysAllEmpty:
    """Edge case: all rows have empty api_key_encrypted."""

    async def test_all_empty_rows_zero_rotated_all_skipped(self) -> None:
        """All-empty rows → 0 rotated, all skipped."""
        old_key = _generate_key()
        new_key = _generate_key()

        rows = [
            _make_row("", provider_name="ollama"),
            _make_row("", provider_name="llama-cpp"),
        ]
        session = _make_mock_session(rows)

        result = await rotate_keys(old_key, new_key, session)

        assert result.total_rows == 2
        assert result.rotated == 0
        assert result.skipped == 2
