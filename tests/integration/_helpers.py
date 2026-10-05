"""Shared helpers for integration tests spanning multiple API test packages.

Plain-function module (not conftest fixtures) — mirrors the ``_helpers.py``
convention used by the wiki and kb integration test packages.
"""

from __future__ import annotations

import uuid


def extract_user_id(auth_headers: dict[str, str]) -> uuid.UUID:
    """Derive the ``auth_headers`` user's id from the JWT sub claim.

    The ``auth_headers`` fixture creates a JWT whose ``sub`` claim is the
    user's UUID.  Decoding it avoids needing a separate ``user_id`` fixture
    that would change the conftest contract.
    """
    import jwt

    from narrare._app.config import get_settings

    token = auth_headers["Authorization"].removeprefix("Bearer ")
    payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    return uuid.UUID(payload["sub"])
