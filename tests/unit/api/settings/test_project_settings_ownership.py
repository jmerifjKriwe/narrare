"""S11a — IDOR regression tests: ownership gate on GET/PATCH /settings/novels.

Router-level + dependency-level matrix for the project-settings surface
(plan ``docs/superpowers/plans/2026-08-26-idor-remediation.md`` §S11a).
Before the fix these routes read and wrote project-keyed
``project_settings`` rows without any ownership check — and
``ProjectSettingsRepository.get`` AUTO-CREATES a row on first read, so a
foreign id even materialized a settings row for the victim (and raised
FK 500s for truly unknown ids).

After the fix (new ``verify_novel_owned`` FastAPI dependency — the plan's
kb-precedent Pattern B): the owner's responses are unchanged; a foreign
or unknown id gets a 404 with ZERO side effects — the gate runs BEFORE
any settings repository is touched. Foreign and unknown ids are
shape-identical (anti-enumeration).

The DB layer is faked via ``FakeDbSession`` (queued ``execute()`` results
— the same contract the repositories' own unit tests use): a queued
``None`` models exactly what the user-scoped ``NovelRepository.get_by_id``
returns for a foreign caller. Sibling matrices (plan §S11b):
``test_token_limits_ownership.py`` and
``test_project_ai_settings_ownership.py``; adaptive:
``tests/unit/api/adaptive/test_adaptive_settings_ownership.py``.
Shared wiring: ``_ownership_helpers.py``.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.settings.dependencies import (
    verify_novel_owned,
    verify_owned_project_scope,
    verify_project_owned,
)
from narrare_core.shared.errors import NotFoundError
from tests.fakes.fake_db_session import FakeDbSession
from tests.unit.api.settings._ownership_helpers import (
    NOVEL_ID,
    USER_A,
    USER_B,
    _existing_settings,
    _novel,
    as_user,
    assert_404_novel,
    cast_session,
    install_session,
)

_PROJECT_URL = "/api/v1/settings/novels/{novel_id}"


# ---------------------------------------------------------------------------
# The gate dependency itself (plan S11a: verify_novel_owned + siblings)
# ---------------------------------------------------------------------------


class TestVerifyNovelOwnedDependency:
    """Direct unit matrix for the new ownership dependencies."""

    async def test_owner_passes(self) -> None:
        session = FakeDbSession(results=[_novel()])
        await verify_novel_owned(
            novel_id=NOVEL_ID,
            session=cast_session(session),
            user_id=str(USER_A),
        )

    async def test_foreign_raises_not_found(self) -> None:
        session = FakeDbSession(results=[None])
        with pytest.raises(NotFoundError) as exc_info:
            await verify_novel_owned(
                novel_id=NOVEL_ID,
                session=cast_session(session),
                user_id=str(USER_B),
            )
        assert str(exc_info.value) == f"Novel ({NOVEL_ID}) not found"

    async def test_unknown_shape_matches_foreign(self) -> None:
        unknown = uuid4()
        session = FakeDbSession(results=[None])
        with pytest.raises(NotFoundError) as exc_info:
            await verify_novel_owned(
                novel_id=unknown,
                session=cast_session(session),
                user_id=str(USER_B),
            )
        assert str(exc_info.value) == f"Novel ({unknown}) not found"

    async def test_project_variant_gates_by_project_id(self) -> None:
        """verify_project_owned: same gate, {project_id}-keyed routes."""
        denied = FakeDbSession(results=[None])
        with pytest.raises(NotFoundError):
            await verify_project_owned(
                project_id=NOVEL_ID,
                session=cast_session(denied),
                user_id=str(USER_B),
            )

        allowed = FakeDbSession(results=[_novel()])
        await verify_project_owned(
            project_id=NOVEL_ID,
            session=cast_session(allowed),
            user_id=str(USER_A),
        )

    async def test_scope_variant_noop_without_project(self) -> None:
        """verify_owned_project_scope: no project scope → no gate (user read)."""
        session = FakeDbSession()
        await verify_owned_project_scope(
            project_id=None,
            session=cast_session(session),
            user_id=str(USER_B),
        )
        assert session.statements == []

    async def test_scope_variant_gates_when_project_given(self) -> None:
        session = FakeDbSession(results=[None])
        with pytest.raises(NotFoundError):
            await verify_owned_project_scope(
                project_id=NOVEL_ID,
                session=cast_session(session),
                user_id=str(USER_B),
            )


# ---------------------------------------------------------------------------
# GET/PATCH /settings/novels/{novel_id} (plan S11a)
# ---------------------------------------------------------------------------


class TestProjectSettingsRoutesOwnership:
    """Owner unchanged; foreign/unknown → 404 with NO settings row created."""

    async def test_owner_get_returns_200(self, app, client) -> None:
        session = install_session(app, _novel(), _existing_settings())

        response = await client.get(_PROJECT_URL.format(novel_id=NOVEL_ID))

        assert response.status_code == 200
        assert response.json()["novel_id"] == str(NOVEL_ID)
        assert session.added == []

    async def test_owner_patch_returns_200(self, app, client) -> None:
        existing = _existing_settings()
        session = install_session(app, _novel(), existing)

        response = await client.patch(
            _PROJECT_URL.format(novel_id=NOVEL_ID), json={"autosave_interval": 120}
        )

        assert response.status_code == 200
        assert response.json()["autosave_interval"] == 120
        assert existing.autosave_interval == 120
        assert session.added == []
        assert session.flush_count >= 1

    async def test_foreign_patch_404_and_no_row_created(self, app, client) -> None:
        """AUTO-CREATE HAZARD: foreign PATCH must not materialize a row.

        ``ProjectSettingsRepository.get`` creates a row on first read —
        the gate must run before the repository is ever touched.
        """
        session = install_session(app, None)
        as_user(app, USER_B)

        response = await client.patch(
            _PROJECT_URL.format(novel_id=NOVEL_ID), json={"autosave_interval": 999}
        )

        assert_404_novel(response, NOVEL_ID)
        assert len(session.statements) == 1  # only the gate's novel lookup
        assert session.added == []
        assert session.flush_count == 0

    async def test_foreign_get_404_and_no_row_created(self, app, client) -> None:
        session = install_session(app, None)
        as_user(app, USER_B)

        response = await client.get(_PROJECT_URL.format(novel_id=NOVEL_ID))

        assert_404_novel(response, NOVEL_ID)
        assert session.added == []

    async def test_unknown_patch_404_shape_matches_foreign(self, app, client) -> None:
        install_session(app, None)
        as_user(app, USER_B)
        unknown = uuid4()

        foreign = await client.patch(
            _PROJECT_URL.format(novel_id=NOVEL_ID), json={"autosave_interval": 999}
        )
        unknown_response = await client.patch(
            _PROJECT_URL.format(novel_id=unknown), json={"autosave_interval": 999}
        )

        assert_404_novel(foreign, NOVEL_ID)
        assert_404_novel(unknown_response, unknown)
