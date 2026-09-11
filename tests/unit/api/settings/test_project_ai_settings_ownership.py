"""S11b — IDOR regression tests: ownership gate on GET/PATCH /settings/ai/novels.

Router-level matrix for the project-AI-override surface (plan
``docs/superpowers/plans/2026-08-26-idor-remediation.md`` §S11b).
Before the fix ``ProjectAiSettingsService.get_settings``/``update_settings``
documented ``user_id`` "(for authorization)" but never used it — a
foreign caller could read and write the victim's model-routing overrides
(which steer the victim project's LLM calls), and the auto-creating
``ProjectAiSettingsRepository.get`` materialized a settings row for
foreign/unknown ids.

After the fix (service-entry gate ``novel_repo.get_by_id(novel_id,
user_id)`` → ``NotFoundError`` BEFORE the repository read): owner
unchanged; foreign or unknown id → 404 with ZERO side effects. Foreign
and unknown ids are shape-identical (anti-enumeration).

The DB layer is faked via ``FakeDbSession`` (queued ``execute()``
results); the REAL service factory + REAL service + REAL repositories
run over the fake session — the full request path is exercised.

Shared wiring: ``_ownership_helpers.py``.
"""

from __future__ import annotations

from uuid import uuid4

from tests.unit.api.settings._ownership_helpers import (
    NOVEL_ID,
    USER_B,
    _existing_settings,
    _novel,
    as_user,
    assert_404_novel,
    install_session,
)

_AI_URL = "/api/v1/settings/ai/novels/{novel_id}"


class TestProjectAiSettingsRoutesOwnership:
    """Owner unchanged; foreign/unknown → 404 before the repo auto-creates."""

    async def test_owner_get_returns_200(self, app, client) -> None:
        session = install_session(app, _novel(), _existing_settings())

        response = await client.get(_AI_URL.format(novel_id=NOVEL_ID))

        assert response.status_code == 200
        assert response.json()["novel_id"] == str(NOVEL_ID)
        assert session.added == []

    async def test_owner_patch_returns_200(self, app, client) -> None:
        existing = _existing_settings()
        session = install_session(app, _novel(), existing)

        response = await client.patch(
            _AI_URL.format(novel_id=NOVEL_ID),
            json={"category_overrides": {"draft": "provider/model"}},
        )

        assert response.status_code == 200
        assert response.json()["category_overrides"] == {"draft": "provider/model"}
        assert existing.category_overrides == {"draft": "provider/model"}
        assert session.added == []

    async def test_foreign_patch_404_and_no_row_created(self, app, client) -> None:
        """Foreign caller must not write model-routing overrides (can
        otherwise redirect the victim project's LLM calls)."""
        session = install_session(app, None)
        as_user(app, USER_B)

        response = await client.patch(
            _AI_URL.format(novel_id=NOVEL_ID),
            json={"category_overrides": {"draft": "evil/provider"}},
        )

        assert_404_novel(response, NOVEL_ID)
        assert len(session.statements) == 1  # only the gate's novel lookup
        assert session.added == []
        assert session.flush_count == 0

    async def test_unknown_get_404_shape_matches_foreign(self, app, client) -> None:
        install_session(app, None)
        as_user(app, USER_B)
        unknown = uuid4()

        foreign = await client.get(_AI_URL.format(novel_id=NOVEL_ID))
        unknown_response = await client.get(_AI_URL.format(novel_id=unknown))

        assert_404_novel(foreign, NOVEL_ID)
        assert_404_novel(unknown_response, unknown)
