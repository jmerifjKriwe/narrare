"""Auth boundary.

One interface, one fixed local implementation. When the hosting model is decided,
only this module changes: routers and repositories already receive a user id.
"""

from uuid import UUID

LOCAL_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


async def current_user_id() -> UUID:
    """FastAPI dependency: the requesting user.

    Local build: every request is the local user. The function is async so a real
    implementation can read a session cookie without changing a single caller.
    """
    return LOCAL_USER_ID
