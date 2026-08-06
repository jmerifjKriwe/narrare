"""RT4 — slug-collision 409 regression tests (Canon ↔ Overlay scope toggle).

These tests pin the REAL production contract that the DB partial unique
indexes enforce (migration 0037):

* ``uq_kb_canon_per_series``  → (series_id, slug) UNIQUE WHERE novel_id IS NULL
* ``uq_kb_overlay_per_novel`` → (novel_id, slug)  UNIQUE WHERE novel_id IS NOT NULL

Before the fix, ``promote_to_canon`` / ``demote_to_overlay`` did NOT check for
an existing same-slug entry in the destination scope before re-scoping. The
collision surfaced as a raw ``IntegrityError`` from the partial index, which
the global handler maps to HTTP 500 — not the typed ``ConflictError`` (409) the
create path (``canon_service.create_canon`` via ``find_canon_by_slug``) and the
join flow (``_join_errors.map_join_integrity_error``) already return. These
endpoints were the asymmetry the CR-04 review surfaced.

The tests exercise :class:`FakeScopeKBRepo` directly. The fake is the unit-test
vehicle (the real repo needs a live Postgres + the partial index); the fake now
ENFORCES the partial-index semantics in pure Python so fake and real can never
diverge again (the CR-04 "documented ≠ implemented" safeguard). The real-repo
parallel regression lives in ``test_scope_repository_mutations.py``; the service
→ HTTP 409 propagation is covered by ``test_scope_endpoints.py``.

Scenarios:

* **Promote collision:** an overlay whose slug matches an EXISTING Canon entry
  of the novel's series → ``ConflictError`` (would violate ``uq_kb_canon_per_series``).
* **Demote collision:** a Canon whose slug matches an EXISTING Overlay of the
  target novel → ``ConflictError`` (would violate ``uq_kb_overlay_per_novel``).
  Uses a single-member series so the D4 Canon-integrity guard is inert
  (relying = 0) and the collision is the sole reason for refusal.
"""

from __future__ import annotations

import uuid
from uuid import uuid4

import pytest

from narrare_core.shared.errors import ConflictError
from tests.fakes.fake_kb_scope_repo import FakeScopeKBRepo


def _seed_series_with_canon_and_member(
    *, canon_slug: str = "magic"
) -> tuple[FakeScopeKBRepo, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Seed a series S with one member novel N1 and a single Canon entry.

    Returns ``(repo, series_id, n1_id, canon_entry_id)``. N1 has NO overlay yet
    — callers add the colliding overlay as needed.
    """
    repo = FakeScopeKBRepo()
    series_id = uuid4()
    n1_id = uuid4()
    canon_entry_id = uuid4()
    repo.seed_entry(
        slug=canon_slug,
        entity_type="system",
        name="Canon Magic",
        entry_id=canon_entry_id,
        novel_id=None,
        series_id=series_id,
    )
    repo.seed_series_members(series_id, [n1_id])
    return repo, series_id, n1_id, canon_entry_id


class TestPromoteSlugCollision:
    """Promoting an overlay whose slug an existing Canon already owns → 409."""

    async def test_promote_into_existing_canon_slug_raises_conflict(self) -> None:
        """N1's overlay 'magic' cannot become Canon — Canon 'magic' exists."""
        repo, _series_id, n1_id, _canon_entry_id = _seed_series_with_canon_and_member()
        overlay = repo.seed_entry(
            slug="magic",
            entity_type="system",
            name="N1 Magic",
            novel_id=n1_id,
            series_id=None,
        )

        with pytest.raises(ConflictError, match="already exists"):
            await repo.promote_to_canon(n1_id, overlay.id)

        # The overlay must remain an overlay (no silent mutation on refusal).
        assert overlay.is_overlay
        assert overlay.novel_id == n1_id


class TestDemoteSlugCollision:
    """Demoting a Canon whose slug an existing Overlay of the target owns → 409."""

    async def test_demote_into_existing_overlay_slug_raises_conflict(self) -> None:
        """Canon 'magic' cannot demote to N1 — N1 already owns overlay 'magic'."""
        repo, series_id, n1_id, canon_entry_id = _seed_series_with_canon_and_member()
        # N1 (the demote target) already carries a 'magic' overlay.
        repo.seed_entry(
            slug="magic",
            entity_type="system",
            name="N1 Magic",
            novel_id=n1_id,
            series_id=None,
        )

        with pytest.raises(ConflictError, match="already exists"):
            await repo.demote_to_overlay(series_id, canon_entry_id, n1_id)

        # The Canon row must remain Canon (no silent mutation on refusal).
        canon_rows = await repo.find_canon_for_series(series_id)
        assert any(e.id == canon_entry_id for e in canon_rows)
