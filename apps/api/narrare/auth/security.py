"""JWT creation/verification and password hashing.

Password hashing uses argon2id (winner of Password Hashing Competition).
See ADR-009 for rationale.

Backward compatibility: verify_password accepts both argon2 and bcrypt hashes
so that any future migration scenario is handled gracefully.  bcrypt is imported
lazily — it is NOT a declared dependency and can be fully removed once all
existing hashes are argon2.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import argon2
import jwt

# Argon2 hasher with sensible defaults (OWASP-recommended parameters)
_hasher = argon2.PasswordHasher(
    time_cost=3,  # iterations
    memory_cost=65536,  # 64 MB
    parallelism=4,  # threads
    hash_len=32,
    salt_len=16,
)


def hash_password(plain: str) -> str:
    """Hash a plaintext password with argon2id."""
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a hash.

    Supports both argon2 and bcrypt hashes for backward compatibility.
    argon2 hashes start with ``$argon2``, bcrypt hashes start with ``$2b$``.
    """
    if hashed.startswith("$argon2"):
        try:
            return _hasher.verify(hashed, plain)
        except argon2.exceptions.VerifyMismatchError:
            return False
        except argon2.exceptions.VerificationError:
            return False

    # Legacy bcrypt support — lazy import since bcrypt is not a dependency.
    if hashed.startswith("$2b$") or hashed.startswith("$2a$"):
        try:
            import bcrypt as _bcrypt  # type: ignore[import-untyped]  # reason: bcrypt has no type stubs (lazy import, optional dependency)

            return bool(_bcrypt.checkpw(plain.encode(), hashed.encode()))  # type: ignore[no-redef]  # reason: checkpw returns Any from untyped bcrypt, triggers false-positive no-redef
        except Exception:
            return False

    # Unknown hash format
    return False


def needs_rehash(hashed: str) -> bool:
    """Check if a hash needs rehashing (parameters changed or was bcrypt)."""
    if hashed.startswith("$argon2"):
        return _hasher.check_needs_rehash(hashed)
    # bcrypt hashes always need rehash
    return True


# ---------------------------------------------------------------------------
# JWT helpers (unchanged)
# ---------------------------------------------------------------------------


def create_access_token(
    subject: str,
    secret_key: str,
    expires_minutes: int = 60,
) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
        "type": "access",
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def create_refresh_token(
    subject: str,
    secret_key: str,
    expires_days: int = 30,
) -> str:
    """Create a signed JWT refresh token."""
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(days=expires_days),
        "type": "refresh",
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def verify_access_token(token: str, secret_key: str) -> dict[str, Any] | None:
    """
    Verify and decode an access token.

    Returns the payload dict, or None if invalid/expired.
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        if payload.get("type") != "access":
            return None
        return payload
    except jwt.PyJWTError:
        return None


def verify_refresh_token(token: str, secret_key: str) -> dict[str, Any] | None:
    """
    Verify and decode a refresh token.

    Returns the payload dict, or None if invalid/expired.
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        if payload.get("type") != "refresh":
            return None
        return payload
    except jwt.PyJWTError:
        return None
