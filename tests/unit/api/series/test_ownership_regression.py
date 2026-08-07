"""RT1 — C1 / IDOR regression tests for the Series + KB ownership surface.

These tests would have caught the original C1 bug surfaced in PR #145's review:
before the fix, ``user_id`` was threaded into the service methods but
**discarded** — every authenticated caller could read or mutate any other
user's series, novels, join/remove operations, and KB scope toggles. The fix
added ``_verify_series_ownership`` (and the sibling novel/series checks on
``KBScopeService``), surfacing every missing-or-not-owned resource as
``ForbiddenError`` (HTTP 403).

The anti-enumeration contract — pinned explicitly here — is stronger than
"raise an error": a *missing* resource and a *not-owned* resource MUST both
surface as ``ForbiddenError`` (403), never ``NotFoundError`` (404), so series
/ novel ids are not enumerable by probing responses.

Each negative case seeds a resource owned by ``USER_A``, invokes the service
method as ``USER_B`` (a different user), and asserts:
  * ``ForbiddenError`` is raised (sibling of ``NotFoundError`` — raising the
    wrong one fails ``pytest.raises(ForbiddenError)``).
  * No mutation reaches the repository (``call_count`` of mutating methods
    stays at 0 — would have caught the original "discard user_id" bug).

Positive sanity checks confirm ``USER_A`` operating on their own resources
still succeeds (no false positives).

Domain dependencies are real in-memory fakes (ADR-030).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from narrare.series.schemas import SeriesSettingsUpdateRequest, SeriesUpdateRequest
from narrare.series.service import SeriesService
from narrare_core.shared.errors import ForbiddenError
from tests.fakes.fake_series_repo import FakeSeriesRepository

if TYPE_CHECKING:
    from narrare_core.series.schemas import Series

# Cross-test-directory import is intentional: ``_scope_service_helpers`` exposes
# its builders as public test API (no leading underscore on the functions) so
# the scope-service fixture can be reused by the ownership regression suite.
from ..kb._scope_service_helpers import build_scope_service
from ._join_helpers import build_owned, make_series, overlay_entry

USER_A = uuid4()
USER_B = uuid4()


# ---------------------------------------------------------------------------
# Shared builders
# ---------------------------------------------------------------------------


def _owned_series_service(
    *, owner: uuid.UUID = USER_A
) -> tuple[SeriesService, FakeSeriesRepository, Series]:
    """Build a ``SeriesService`` + a Series owned by ``owner`` (no novels).

    Returns the wired ``FakeSeriesRepository`` so tests can assert on
    ``call_count`` without reaching into the service's private ``_repo``.
    """
    series = make_series(user_id=owner)
    repo = FakeSeriesRepository()
    repo.seed(series)
    return SeriesService(repo), repo, series


# ---------------------------------------------------------------------------
# SeriesService — every public method must enforce ownership (C1)
# ---------------------------------------------------------------------------


class TestSeriesServiceOwnershipIDOR:
    """Each SeriesService method rejects a cross-user caller (403, no mutation)."""

    async def test_get_series_rejects_cross_user(self) -> None:
        service, _, series = _owned_series_service()
        with pytest.raises(ForbiddenError):
            await service.get_series(series.id, USER_B)

    async def test_update_series_rejects_cross_user(self) -> None:
        service, repo, series = _owned_series_service()
        with pytest.raises(ForbiddenError):
            await service.update_series(series.id, USER_B, SeriesUpdateRequest(title="Hacked"))
        assert repo.call_count("update") == 0

    async def test_delete_series_rejects_cross_user(self) -> None:
        service, repo, series = _owned_series_service()
        with pytest.raises(ForbiddenError):
            await service.delete_series(series.id, USER_B)
        # Neither the series row nor the Canon bulk-delete may be touched.
        assert repo.call_count("delete") == 0
        assert repo.call_count("delete_canon_for_series") == 0

    async def test_get_settings_rejects_cross_user(self) -> None:
        service, _, series = _owned_series_service()
        with pytest.raises(ForbiddenError):
            await service.get_settings(series.id, USER_B)

    async def test_update_settings_rejects_cross_user(self) -> None:
        service, repo, series = _owned_series_service()
        with pytest.raises(ForbiddenError):
            await service.update_settings(
                series.id, USER_B, SeriesSettingsUpdateRequest(author_voice={"tone": "x"})
            )
        assert repo.call_count("update_settings") == 0

    async def test_list_novels_rejects_cross_user(self) -> None:
        service, repo, series = _owned_series_service()
        with pytest.raises(ForbiddenError):
            await service.list_novels(series.id, USER_B)
        assert repo.call_count("list_novels") == 0

    async def test_reorder_novels_rejects_cross_user(self) -> None:
        service, repo, series = _owned_series_service()
        with pytest.raises(ForbiddenError):
            await service.reorder_novels(series.id, USER_B, [uuid4()])
        assert repo.call_count("reorder_novels") == 0


class TestSeriesServiceOwnerSucceeds:
    """Sanity: the legitimate owner's calls are NOT false-positively rejected."""

    async def test_owner_get_series_returns_response(self) -> None:
        service, _, series = _owned_series_service()
        result = await service.get_series(series.id, USER_A)
        assert result.id == series.id
        assert result.user_id == USER_A


# ---------------------------------------------------------------------------
# Anti-enumeration: a *missing* series surfaces as 403, NOT 404
# ---------------------------------------------------------------------------


class TestAntiEnumeration:
    """A nonexistent series id must surface as ForbiddenError, not NotFoundError.

    ``ForbiddenError`` and ``NotFoundError`` are sibling subclasses of
    ``NarrareError`` — ``pytest.raises(ForbiddenError)`` fails if the service
    raises ``NotFoundError`` instead, which is exactly the regression that
    would re-enable series-id enumeration via 404 vs 403 probing.
    """

    async def test_get_series_missing_id_raises_forbidden_not_not_found(self) -> None:
        service = SeriesService(FakeSeriesRepository())
        with pytest.raises(ForbiddenError):
            await service.get_series(uuid4(), USER_A)


# ---------------------------------------------------------------------------
# SeriesJoinService — preview / apply / remove must verify ownership (C1)
# ---------------------------------------------------------------------------


class TestSeriesJoinServiceOwnershipIDOR:
    """Join-service methods reject a caller who lacks series/novel ownership."""

    async def test_preview_join_rejects_cross_user_series(self) -> None:
        """USER_B owns the novel but not USER_A's series → 403 on series check."""
        service, _, _, _, _, series, _ = build_owned(user_id=USER_A)
        b_novel_id = uuid4()
        with pytest.raises(ForbiddenError):
            await service.preview_join(series.id, b_novel_id, USER_B)

    async def test_apply_join_rejects_cross_user_series(self) -> None:
        service, session, _, _, _, series, _ = build_owned(user_id=USER_A)
        b_novel_id = uuid4()
        with pytest.raises(ForbiddenError):
            await service.apply_join(series.id, b_novel_id, position=1, user_id=USER_B)
        assert session.commit_count == 0

    async def test_remove_novel_rejects_cross_user_series(self) -> None:
        """USER_B tries to remove USER_A's novel from USER_A's series → 403."""
        service, session, _, _, _, series, a_novel_id = build_owned(user_id=USER_A)
        with pytest.raises(ForbiddenError):
            await service.remove_novel(series.id, a_novel_id, USER_B)
        assert session.commit_count == 0


class TestSeriesJoinServiceOwnerSucceeds:
    """Sanity: the legitimate owner's preview_join returns a result."""

    async def test_owner_preview_join_returns_preview(self) -> None:
        service, _, _, kb_repo, _, series, novel_id = build_owned(user_id=USER_A)
        kb_repo.seed_overlay(novel_id, [overlay_entry(novel_id, entity_type="system")])

        preview = await service.preview_join(series.id, novel_id, USER_A)

        assert preview.series_id == series.id
        assert preview.novel_id == novel_id


# ---------------------------------------------------------------------------
# KBScopeService — promote / demote must verify ownership (C1)
# ---------------------------------------------------------------------------


class TestKBScopeServiceOwnershipIDOR:
    """Scope-toggle methods reject a caller who lacks novel/series ownership."""

    async def test_promote_to_canon_rejects_cross_user_novel(self) -> None:
        """USER_B tries to promote an entry on USER_A's novel → 403."""
        fx = build_scope_service(user_id=USER_A)
        entry_id = uuid4()
        with pytest.raises(ForbiddenError):
            await fx.service.promote_to_canon(fx.novel_id, entry_id, USER_B)
        assert fx.kb_repo.promote_calls == []

    async def test_demote_to_overlay_rejects_cross_user_series(self) -> None:
        """USER_B tries to demote a canon entry of USER_A's series → 403."""
        fx = build_scope_service(user_id=USER_A)
        entry_id = uuid4()
        with pytest.raises(ForbiddenError):
            await fx.service.demote_to_overlay(fx.series_id, entry_id, fx.target_novel_id, USER_B)
        assert fx.kb_repo.demote_calls == []
