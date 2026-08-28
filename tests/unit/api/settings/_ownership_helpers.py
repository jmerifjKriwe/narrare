"""S11 — shared helpers for the settings ownership matrices.

Common wiring for the IDOR regression suites (plan §S11): identities,
queued-session builders, and the anti-enumeration 404 assertion. The
``app``/``client`` fixtures live in ``conftest.py`` (pytest discovers
fixtures only there or in the test module itself).

A queued ``None`` models exactly what the user-scoped
``NovelRepository.get_by_id`` returns for a foreign caller (the same
contract the repositories' own unit tests use).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from fastapi import status

from narrare.novels.models import Novel
from narrare.settings.models import ProjectSettings
from tests.fakes.fake_db_session import FakeDbSession

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

USER_A = uuid4()  # rightful owner of the novel (the victim)
USER_B = uuid4()  # foreign caller

NOVEL_ID = uuid4()  # owned by USER_A (novel ≡ project on these surfaces)


def _novel(novel_id: UUID = NOVEL_ID, owner: UUID = USER_A) -> Novel:
    """A novel row as the gate's ownership lookup would return it."""
    return Novel(id=novel_id, user_id=owner)


def _existing_settings() -> ProjectSettings:
    """A fully populated project-settings row (response-required fields set).

    ``ProjectSettingsResponse`` requires every column; ORM ``default=``
    values only apply at INSERT, so the fake existing row sets them
    explicitly.
    """
    return ProjectSettings(
        novel_id=NOVEL_ID,
        autosave_interval=30,
        default_language="en",
        ai_provider="",
        ai_model="",
        model_overrides="{}",
        category_overrides={},
        intent_overrides={},
        token_limit_overrides={},
        use_series_voice=True,
        updated_at=datetime.now(UTC),
    )


def cast_session(session: FakeDbSession) -> AsyncSession:
    """Type-bridge the fake into the dependency's SessionDep parameter."""
    return cast("AsyncSession", session)


def install_session(app: FastAPI, *queued: object) -> FakeDbSession:
    """Override the session dependency with a queued-result fake."""
    from narrare._app.database import get_async_session

    session = FakeDbSession(results=list(queued))
    app.dependency_overrides[get_async_session] = lambda: session
    return session


def as_user(app: FastAPI, user_id: UUID) -> None:
    """Switch the mocked caller identity."""
    app.state.auth_user = str(user_id)


def assert_404_novel(response, novel_id: UUID) -> None:
    """Foreign ≡ unknown: the sanctioned anti-enumeration 404 shape."""
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": f"Novel ({novel_id}) not found", "code": "NOT_FOUND"}
