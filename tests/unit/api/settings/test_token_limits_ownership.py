"""S11b — IDOR regression tests: ownership gate on the token-limits surfaces.

Router-level matrix for PUT ``/settings/token-limits/project/{project_id}``
and GET ``/settings/token-limits/?project_id=…`` (plan
``docs/superpowers/plans/2026-08-26-idor-remediation.md`` §S11b). Before
the fix ``update_project_limits`` accepted ANY string as ``project_id``
with no ownership check — a foreign caller could overwrite the victim's
token-limit overrides, and the auto-creating project read materialized a
row for unknown ids.

After the fix (``verify_project_owned`` path dependency +
``verify_owned_project_scope`` query-scope dependency, ``project_id``
UUID-typed): owner unchanged (incl. first-touch auto-create); foreign or
unknown id → 404 with ZERO side effects; arbitrary non-UUID strings are
a 422, never a write.

The route previously mounted at a DOUBLED prefix
(``/settings/settings/token-limits/…`` — the sub-router re-declared the
parent's ``/settings`` prefix) and was unreachable at the path the
frontend calls; the S11b fix corrected the mounting (see
``settings/token_limits/router.py``).

Shared wiring: ``_ownership_helpers.py``.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import status

from narrare.settings.token_limits.models import ProjectTokenLimits, UserTokenLimits
from tests.unit.api.settings._ownership_helpers import (
    NOVEL_ID,
    USER_A,
    USER_B,
    _novel,
    as_user,
    assert_404_novel,
    install_session,
)

_TOKEN_PROJECT_URL = "/api/v1/settings/token-limits/project/{project_id}"
_TOKEN_ROOT_URL = "/api/v1/settings/token-limits/"


class TestTokenLimitsRoutesOwnership:
    """Owner unchanged (incl. first-touch auto-create); foreign/unknown → 404."""

    async def test_owner_put_204_first_touch_creates_row(self, app, client) -> None:
        """Owner PUT on a project without a row auto-creates it (unchanged).

        Adapted to the main-branch upsert mechanism (race fix): the row is
        materialized via ``pg_insert ... ON CONFLICT DO NOTHING`` and comes
        back from the post-upsert re-select — not from ``session.add`` —
        so the fake queues the re-select result instead.
        """
        row = ProjectTokenLimits(project_id=str(NOVEL_ID), overrides={})
        # The row result is consumed twice: once by the upsert statement,
        # once by the post-upsert re-select.
        install_session(app, _novel(), None, row, row)

        response = await client.put(
            _TOKEN_PROJECT_URL.format(project_id=NOVEL_ID), json={"output_limit": 2048}
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert row.project_id == str(NOVEL_ID)
        assert row.overrides == {"output_limit": 2048}

    async def test_foreign_put_404_and_no_row_created(self, app, client) -> None:
        session = install_session(app, None)
        as_user(app, USER_B)

        response = await client.put(
            _TOKEN_PROJECT_URL.format(project_id=NOVEL_ID), json={"output_limit": 2048}
        )

        assert_404_novel(response, NOVEL_ID)
        assert len(session.statements) == 1
        assert session.added == []
        assert session.flush_count == 0

    async def test_unknown_put_404_shape_matches_foreign(self, app, client) -> None:
        install_session(app, None)
        as_user(app, USER_B)
        unknown = uuid4()

        foreign = await client.put(
            _TOKEN_PROJECT_URL.format(project_id=NOVEL_ID), json={"output_limit": 2048}
        )
        unknown_response = await client.put(
            _TOKEN_PROJECT_URL.format(project_id=unknown), json={"output_limit": 2048}
        )

        assert_404_novel(foreign, NOVEL_ID)
        assert_404_novel(unknown_response, unknown)

    async def test_put_non_uuid_project_id_422(self, app, client) -> None:
        """Typed path param: arbitrary strings no longer reach the store."""
        response = await client.put(
            _TOKEN_PROJECT_URL.format(project_id="not-a-uuid"), json={"output_limit": 1}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_get_with_owner_project_200(self, app, client) -> None:
        install_session(
            app,
            _novel(),
            ProjectTokenLimits(project_id=str(NOVEL_ID), overrides={"output_limit": 1234}),
            UserTokenLimits(user_id=str(USER_A)),
        )

        response = await client.get(_TOKEN_ROOT_URL, params={"project_id": str(NOVEL_ID)})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["output_limit"] == 1234

    async def test_get_with_foreign_project_404_and_no_row_created(self, app, client) -> None:
        """READ auto-create hazard: the resolved-limits GET materializes a
        project row when given an unknown id — the scope gate closes it."""
        session = install_session(app, None)
        as_user(app, USER_B)

        response = await client.get(_TOKEN_ROOT_URL, params={"project_id": str(NOVEL_ID)})

        assert_404_novel(response, NOVEL_ID)
        assert len(session.statements) == 1  # project + user reads never ran
        assert session.added == []

    async def test_get_without_project_scope_200_user_only(self, app, client) -> None:
        """No project scope → no gate: the user-level read is unaffected."""
        install_session(app, UserTokenLimits(user_id=str(USER_A)))

        response = await client.get(_TOKEN_ROOT_URL)

        assert response.status_code == status.HTTP_200_OK
