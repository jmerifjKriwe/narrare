"""RT3 — D4 demote-409 regression tests (Canon-integrity guard).

These tests would have caught the original D4 bug surfaced in PR #145's review:
before the fix, demoting a Canon entry that other member novels relied on
succeeded silently — those novels lost the entry from their merged view
without warning. The fix added the Canon-integrity guard in
:meth:`KBScopeRepository.demote_to_overlay`: if any OTHER member novel has no
own Overlay with the demoted entry's slug, the demotion is refused with
``ConflictError`` (HTTP 409) — no silent breakage (RULE-11).

Scenarios pin the contract at the service layer (real in-memory fake with real
D4 logic + partial-index enforcement, ADR-030):

* **Scenario A (409, D4 guard):** N2 is a member of series S, has no overlay
  for the Canon slug, and so "relies" on the Canon. Demoting Canon entry E to
  N1 would drop E from N2's merged view → ``ConflictError``.
* **Scenario B (409, slug collision):** BOTH N1 and N2 carry an overlay with
  the same slug. The D4 guard passes (N2 is covered), but demoting Canon E to
  N1 would collide with N1's existing overlay (``uq_kb_overlay_per_novel``) →
  ``ConflictError``. This was previously a FALSE POSITIVE that asserted the
  demote "succeeds" only because the fake did not enforce the partial index.

The D4 logic lives in the repository; the service delegates unchanged. The
fake (:mod:`tests.fakes.fake_kb_scope_repo`) mirrors the real
``_count_relying_novels`` SQL line-for-line in pure Python AND enforces the
``uq_kb_canon_per_series`` / ``uq_kb_overlay_per_novel`` partial-index
semantics, so a divergence between the fake's contract and the repo's would
surface in integration (CR-04 safeguard).
"""

from __future__ import annotations

import uuid
from uuid import uuid4

import pytest

from narrare.kb.scope_service import KBScopeService
from narrare_core.kb.schemas.entry import NovelKBEntry, SeriesKBEntry
from narrare_core.series.schemas import Series
from narrare_core.shared.errors import ConflictError, ForbiddenError
from tests.fakes.fake_kb_scope_repo import FakeScopeKBRepo
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository

USER_ID = uuid4()


def _build_d4_service(
    *, n1_has_overlay: bool, n2_has_overlay: bool
) -> tuple[KBScopeService, FakeScopeKBRepo, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Wire a KBScopeService over the D4 fake, seeded with the canon + 2 novels.

    Series S (owned by ``USER_ID``) has members N1, N2. A single Canon entry E
    (slug "magic") sits on S. Depending on the flags, N1 and/or N2 also carry
    an overlay with slug "magic" — the input to the D4 relying count.

    Returns ``(service, kb_repo, series_id, n1_id, n2_id, canon_entry_id)``.
    """
    series_id = uuid4()
    n1_id, n2_id = uuid4(), uuid4()
    canon_entry_id = uuid4()

    kb_repo = FakeScopeKBRepo()
    kb_repo.seed_entry(
        slug="magic",
        entity_type="system",
        name="Magic System",
        entry_id=canon_entry_id,
        novel_id=None,
        series_id=series_id,
    )
    if n1_has_overlay:
        kb_repo.seed_entry(
            slug="magic",
            entity_type="system",
            name="N1 Magic",
            novel_id=n1_id,
            series_id=None,
        )
    if n2_has_overlay:
        kb_repo.seed_entry(
            slug="magic",
            entity_type="system",
            name="N2 Magic",
            novel_id=n2_id,
            series_id=None,
        )
    kb_repo.seed_series_members(series_id, [n1_id, n2_id])

    novel_repo = FakeNovelRepository()
    from tests.factories import make_novel

    novel_repo.seed(make_novel(id=n1_id, user_id=USER_ID, series_id=series_id, series_position=1))
    novel_repo.seed(make_novel(id=n2_id, user_id=USER_ID, series_id=series_id, series_position=2))

    series_repo = FakeSeriesRepository()
    series_repo.seed(Series(id=series_id, user_id=USER_ID, title="Test Series"))

    service = KBScopeService(kb_repo, novel_repo, series_repo)
    return service, kb_repo, series_id, n1_id, n2_id, canon_entry_id


# ---------------------------------------------------------------------------
# Scenario A — demotion refused when another novel relies on the Canon (409)
# ---------------------------------------------------------------------------


class TestDemoteCanonIntegrityGuard:
    """D4: demoting a relied-on Canon entry is refused with 409."""

    async def test_demote_raises_conflict_when_other_novel_relies_on_canon(self) -> None:
        """N2 has no overlay → relies on Canon → demoting to N1 is refused."""
        service, kb_repo, series_id, n1_id, _n2_id, canon_entry_id = _build_d4_service(
            n1_has_overlay=False, n2_has_overlay=False
        )

        with pytest.raises(ConflictError, match="rely on it"):
            await service.demote_to_overlay(series_id, canon_entry_id, n1_id, USER_ID)

        # The Canon row is untouched (no silent mutation alongside the refusal).
        assert kb_repo.demote_calls == [(series_id, canon_entry_id, n1_id)]
        canon_rows = await kb_repo.find_canon_for_series(series_id)
        assert any(e.id == canon_entry_id for e in canon_rows)

    async def test_demote_propagates_when_only_target_lacks_overlay(self) -> None:
        """Target N1 has no overlay, but N2 does → still refused (target excluded).

        The D4 check excludes the target novel — what matters is whether
        OTHER members rely on the Canon. Here N2 is covered (has its own
        overlay), so the demotion succeeds (Scenario B, cross-referenced).
        """
        service, _, series_id, n1_id, _, canon_entry_id = _build_d4_service(
            n1_has_overlay=False, n2_has_overlay=True
        )

        # Succeeds because the only OTHER member (N2) carries its own overlay.
        result = await service.demote_to_overlay(series_id, canon_entry_id, n1_id, USER_ID)

        assert isinstance(result, NovelKBEntry)
        assert result.novel_id == n1_id


# ---------------------------------------------------------------------------
# Scenario B — demote refused on slug collision with the target's overlay (409)
# ---------------------------------------------------------------------------


class TestDemoteSlugCollision:
    """Demoting a Canon whose slug the target novel already owns → 409.

    The scenario that was previously a FALSE POSITIVE (it asserted the demote
    "succeeds" only because ``FakeScopeKBRepo`` did not enforce the partial
    unique index). With both members carrying a same-slug overlay, demoting the
    Canon to N1 collides with N1's existing overlay (``uq_kb_overlay_per_novel``,
    migration 0037). The D4 Canon-integrity guard passes (N2 is covered), so the
    collision is the sole reason the demotion is refused.
    """

    async def test_demote_into_existing_target_slug_raises_conflict(self) -> None:
        """Both N1 and N2 carry a 'magic' overlay → demoting Canon 'magic' to N1
        collides with N1's overlay → ConflictError (HTTP 409), Canon untouched."""
        service, kb_repo, series_id, n1_id, _, canon_entry_id = _build_d4_service(
            n1_has_overlay=True, n2_has_overlay=True
        )

        with pytest.raises(ConflictError, match="already exists"):
            await service.demote_to_overlay(series_id, canon_entry_id, n1_id, USER_ID)

        # The Canon row is untouched (no silent mutation alongside the refusal).
        canon_rows = await kb_repo.find_canon_for_series(series_id)
        assert any(e.id == canon_entry_id for e in canon_rows)


# ---------------------------------------------------------------------------
# Ownership still fires before D4 (anti-bypass: 403 never masked by 409)
# ---------------------------------------------------------------------------


class TestDemoteOwnershipBeforeGuard:
    """Ownership (403) is verified before the D4 guard (409) — both must work."""

    async def test_demote_cross_user_still_raises_forbidden(self) -> None:
        """A cross-user caller is rejected before the D4 logic runs (no 409 leak)."""
        service, kb_repo, series_id, n1_id, _, canon_entry_id = _build_d4_service(
            n1_has_overlay=False, n2_has_overlay=False
        )
        other_user = uuid4()

        with pytest.raises(ForbiddenError):
            await service.demote_to_overlay(series_id, canon_entry_id, n1_id, other_user)

        # The D4 guard was never reached (no demote call recorded by the fake).
        assert [c for c in kb_repo.calls if c.method == "demote_to_overlay"] == []


# ---------------------------------------------------------------------------
# Sanity: the demoted entry's shape matches the Core overlay type
# ---------------------------------------------------------------------------


def test_demote_result_is_overlay_scope() -> None:
    """Programmatic sanity: the Core NovelKBEntry type carries novel_id, not series_id."""
    entry = NovelKBEntry(
        id=uuid4(),
        entity_type="system",
        name="X",
        slug="x",
        novel_id=uuid4(),
    )
    assert entry.novel_id is not None
    assert not hasattr(entry, "series_id") or entry.series_id is None  # type: ignore[attr-defined]


def test_canon_result_is_canon_scope() -> None:
    """Programmatic sanity: the Core SeriesKBEntry type carries series_id."""
    sid = uuid4()
    entry = SeriesKBEntry(
        id=uuid4(),
        entity_type="system",
        name="X",
        slug="x",
        series_id=sid,
    )
    assert entry.series_id == sid
    assert entry.novel_id is None
