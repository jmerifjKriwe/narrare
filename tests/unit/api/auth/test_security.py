"""Unit tests for auth/security.py — argon2 password hashing and JWT tokens."""

from __future__ import annotations

from typing import TYPE_CHECKING

from structlog.testing import capture_logs

from narrare.auth.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    needs_rehash,
    verify_access_token,
    verify_password,
    verify_refresh_token,
)

if TYPE_CHECKING:
    import pytest

SECRET = "test-secret-key-at-least-32-chars-long"


class TestPasswordHashing:
    """Tests for argon2 password hashing."""

    def test_hash_is_not_plaintext(self) -> None:
        hashed = hash_password("mysecret")
        assert hashed != "mysecret"

    def test_hash_starts_with_argon2_prefix(self) -> None:
        hashed = hash_password("mysecret")
        assert hashed.startswith("$argon2")

    def test_verify_correct_password(self) -> None:
        hashed = hash_password("mysecret")
        assert verify_password("mysecret", hashed) is True

    def test_verify_wrong_password(self) -> None:
        hashed = hash_password("mysecret")
        assert verify_password("wrongpassword", hashed) is False

    def test_same_password_different_hashes(self) -> None:
        h1 = hash_password("password")
        h2 = hash_password("password")
        assert h1 != h2  # argon2 generates unique salts

    def test_verify_unknown_hash_format_returns_false(self) -> None:
        assert verify_password("anything", "$unknown$hash") is False

    def test_verify_legacy_bcrypt_without_library_returns_false(self) -> None:
        """A bcrypt hash without bcrypt installed should return False gracefully."""
        fake_bcrypt_hash = "$2b$12$invalidhashvaluethatisnotreal"
        assert verify_password("anything", fake_bcrypt_hash) is False


class TestNeedsRehash:
    """Tests for the needs_rehash function."""

    def test_argon2_hash_does_not_need_rehash(self) -> None:
        hashed = hash_password("mysecret")
        assert needs_rehash(hashed) is False

    def test_bcrypt_hash_always_needs_rehash(self) -> None:
        assert needs_rehash("$2b$12$somehash") is True

    def test_bcrypt_2a_hash_always_needs_rehash(self) -> None:
        assert needs_rehash("$2a$12$somehash") is True

    def test_unknown_hash_always_needs_rehash(self) -> None:
        assert needs_rehash("$unknown$hash") is True


class TestAccessToken:
    def test_create_and_verify(self) -> None:
        token = create_access_token("user-123", SECRET)
        payload = verify_access_token(token, SECRET)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"

    def test_expired_token_returns_none(self) -> None:
        token = create_access_token("user-123", SECRET, expires_minutes=-1)
        assert verify_access_token(token, SECRET) is None

    def test_wrong_secret_returns_none(self) -> None:
        token = create_access_token("user-123", SECRET)
        # Use a different secret of the same length to avoid InsecureKeyLengthWarning
        assert verify_access_token(token, SECRET + "different") is None

    def test_refresh_token_fails_access_verification(self) -> None:
        token = create_refresh_token("user-123", SECRET)
        # Using refresh token where access token expected
        assert verify_access_token(token, SECRET) is None


class TestRefreshToken:
    def test_create_and_verify(self) -> None:
        token = create_refresh_token("user-123", SECRET)
        payload = verify_refresh_token(token, SECRET)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["type"] == "refresh"

    def test_access_token_fails_refresh_verification(self) -> None:
        token = create_access_token("user-123", SECRET)
        assert verify_refresh_token(token, SECRET) is None


class TestVerifyPasswordExceptionHandling:
    """Regression tests for ADR-009 Addendum: exception handling policy.

    These tests pin the RULE-11 fix: transient argon2 errors and corrupt
    hashes must be logged (not silently swallowed), while expected password
    mismatches must NOT log (no noise). All paths return False → 401 →
    no account-existence oracle.

    structlog events are captured via ``structlog.testing.capture_logs``
    (the project's established pattern — unit tests never call
    ``configure_logging()``, so ``caplog`` cannot see structlog events).
    """

    def test_transient_verification_error_logged_and_returns_false(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Transient VerificationError must be logged, not silently swallowed.

        A transient argon2 internal failure (e.g. memory/thread allocation
        under CI contention) raises ``VerificationError`` (the base class,
        not ``VerifyMismatchError``). The current code catches this and
        returns ``False`` WITHOUT logging → RULE-11 violation.
        """
        import argon2

        # Create a real hash before patching verify.
        hashed = hash_password("testpassword")

        # PasswordHasher uses __slots__, so we patch the CLASS method
        # (not the instance). A plain function (not MagicMock) is used
        # to avoid RULE-TEST-01 (bare MagicMock without spec=). When set
        # as a class attribute, Python's descriptor protocol binds it,
        # so the first arg is the instance (self).
        def _raise_transient(_self: object, _hash: str, _plain: str) -> bool:
            raise argon2.exceptions.VerificationError("transient")

        monkeypatch.setattr(argon2.PasswordHasher, "verify", _raise_transient)

        with capture_logs() as logs:
            result = verify_password("testpassword", hashed)

        assert result is False
        assert any(r.get("event") == "password_verification_transient_failure" for r in logs), (
            "Transient VerificationError must be logged at ERROR level"
        )

    def test_invalid_hash_error_logged_and_returns_false(self) -> None:
        """InvalidHashError (corrupt hash) must be logged and return False.

        ``"$argon2"`` starts with ``$argon2`` (enters the argon2 branch) but
        is too short to be a valid hash → argon2 raises ``InvalidHashError``
        (a ``ValueError`` subclass, NOT a ``VerificationError`` subclass).
        The current code does not catch ``InvalidHashError`` at all → it
        propagates unhandled.
        """
        with capture_logs() as logs:
            result = verify_password("testpassword", "$argon2")

        assert result is False
        assert any(r.get("event") == "password_hash_invalid" for r in logs), (
            "InvalidHashError must be logged at ERROR level"
        )

    def test_mismatch_returns_false_without_error_log(self) -> None:
        """VerifyMismatchError (wrong password) returns False without ERROR log.

        Guard test: ensures we don't add ERROR-level logging for expected
        password mismatches (which would create log noise on every wrong
        login attempt). This test passes against BOTH the current and fixed
        code — it guards against over-logging.
        """
        hashed = hash_password("correct")
        with capture_logs() as logs:
            result = verify_password("wrong", hashed)

        assert result is False
        assert not any(r.get("log_level") == "error" for r in logs), (
            "Expected mismatch must not log at ERROR level"
        )

    def test_production_hasher_uses_owasp_params(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Production environment must use OWASP-recommended hasher params.

        Regression test: the test hasher (lighter params) must NEVER
        activate in production. When ``ENVIRONMENT=production``, ``_get_hasher()``
        must return the OWASP-param hasher (64 MB, 4 threads).
        """
        from narrare._app.config import get_settings
        from narrare.auth.security import _get_hasher

        monkeypatch.setenv("ENVIRONMENT", "production")
        get_settings.cache_clear()
        try:
            hasher = _get_hasher()
            assert hasher.memory_cost == 65536  # 64 MB
            assert hasher.time_cost == 3
            assert hasher.parallelism == 4
        finally:
            get_settings.cache_clear()

    def test_test_hasher_uses_lighter_params(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test environment uses lighter hasher params to reduce flake surface.

        When ``ENVIRONMENT=test``, ``_get_hasher()`` must return the lighter
        hasher (8 MB, 1 thread) to reduce the argon2 allocation flake surface
        under CI contention.
        """
        from narrare._app.config import get_settings
        from narrare.auth.security import _get_hasher

        monkeypatch.setenv("ENVIRONMENT", "test")
        get_settings.cache_clear()
        try:
            hasher = _get_hasher()
            assert hasher.memory_cost == 8192  # 8 MB
            assert hasher.time_cost == 1
            assert hasher.parallelism == 1
        finally:
            get_settings.cache_clear()
