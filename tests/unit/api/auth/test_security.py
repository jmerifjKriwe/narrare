"""Unit tests for auth/security.py"""

from __future__ import annotations

from narrare.auth.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_access_token,
    verify_password,
    verify_refresh_token,
)

SECRET = "test-secret-key-at-least-32-chars-long"


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self) -> None:
        hashed = hash_password("mysecret")
        assert hashed != "mysecret"

    def test_verify_correct_password(self) -> None:
        hashed = hash_password("mysecret")
        assert verify_password("mysecret", hashed) is True

    def test_verify_wrong_password(self) -> None:
        hashed = hash_password("mysecret")
        assert verify_password("wrongpassword", hashed) is False

    def test_same_password_different_hashes(self) -> None:
        h1 = hash_password("password")
        h2 = hash_password("password")
        assert h1 != h2  # bcrypt generates unique salts


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
