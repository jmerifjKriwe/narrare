"""RT2 — C2 cascade-survival regression test (real DB, alembic-migrated schema).

This test would have caught the original C2 bug from PR #145's review: before
the fix, ``kb_entries.series_id`` was declared ``ON DELETE CASCADE`` at the DB
level, so deleting a series silently destroyed every Novel-Overlay KB row
attached to that series — a destructive data-loss path masquerading as a clean
series delete. The fix has two halves, both asserted here:

1. **Migration 0037** declares ``kb_entries.series_id`` as ``ON DELETE SET
   NULL`` at the DB level (lines 174-176 — the migration is authoritative for
   runtime DB shape; the ORM ``models.py`` declaration on line 44 still says
   ``ondelete="CASCADE"``, a documentation drift that does not affect runtime
   because ``Base.metadata.create_all()`` is forbidden in integration tests).
   A series delete leaves the novel's overlay KB rows intact as standalone-
   novel entries.
2. **``SeriesService.delete_series``** removes the Canon rows
   (``novel_id IS NULL``) in-transaction before the series row — Canon has no
   home without its series (the scope-invariant CHECK forbids it), so SET NULL
   is intentionally not the Canon fate.

Setup note — entry E is created as a Novel-Overlay, then round-tripped through
``promote_to_canon`` → ``demote_to_overlay`` to arrive back at the "E is an
overlay on N" state. This exercises the real scope-mutation flow end-to-end
and serves as the regression for the ``MissingGreenlet`` crash that occurred
when those methods called ``_flush()`` instead of ``_flush_and_refresh()``
(reading ``updated_at`` after flush without refresh triggered a synchronous
lazy-load under ``AsyncSession``).

Scenario walked end-to-end against the real Postgres DB:

1. Create series S (user A), novel N (user A, member of S).
2. Create overlay KB entry E on N (novel_id=N, series_id=NULL).
3. Create Canon KB entry C on S (novel_id=NULL, series_id=S).
4. Create standalone KB entry O on N (unrelated slug).
5. Promote E to Canon, then demote E back to Overlay on N (scope-mutation
   round-trip — regression for the MissingGreenlet crash).
6. ``SeriesService.delete_series(S)``.
7-11. Assert post-conditions (see test body).

Uses the rolled-back ``db_session`` fixture (RULE-14: schema from real
``alembic upgrade head``, never ``create_all()``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy

from narrare.kb.models import KBEntry
from narrare.kb.repository import KBRepository
from narrare.series.repository import SeriesRepository
from narrare.series.service import SeriesService

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Seed helpers — raw SQL inserts for the parent rows the FKs need
# (mirrors the pattern in tests/integration/kb/test_kb_embedding_hooks.py).
# ---------------------------------------------------------------------------


async def _seed_user(db_session: AsyncSession, user_id: uuid.UUID) -> None:
    """Insert a minimal users row (every FK we use traces back here)."""
    await db_session.execute(
        sqlalchemy.text(
            "INSERT INTO users (id, email, hashed_password, created_at, updated_at) "
            "VALUES (:id, :email, 'fake_hash', now(), now())"
        ),
        {"id": str(user_id), "email": f"u-{user_id.hex[:10]}@example.com"},
    )


async def _seed_series(
    db_session: AsyncSession, *, series_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Insert a series row + its 1:1 series_settings row (the 1:1 invariant)."""
    import uuid as _uuid

    await db_session.execute(
        sqlalchemy.text(
            "INSERT INTO series (id, user_id, title, status, created_at, updated_at) "
            "VALUES (:id, :user_id, 'RT2 Series', 'draft', now(), now())"
        ),
        {"id": str(series_id), "user_id": str(user_id)},
    )
    # series_settings has a 1:1 invariant + NOT NULL FK → seed a row explicitly.
    await db_session.execute(
        sqlalchemy.text(
            "INSERT INTO series_settings (id, series_id, created_at, updated_at) "
            "VALUES (:id, :series_id, now(), now())"
        ),
        {"id": str(_uuid.uuid4()), "series_id": str(series_id)},
    )


async def _seed_novel_member(
    db_session: AsyncSession,
    *,
    novel_id: uuid.UUID,
    user_id: uuid.UUID,
    series_id: uuid.UUID,
    position: int,
) -> None:
    """Insert a novels row with series membership set."""
    await db_session.execute(
        sqlalchemy.text(
            "INSERT INTO novels "
            "(id, user_id, title, author, genre, writing_language, tone, "
            " story_structure, logline, synopsis, is_demo, "
            " series_id, series_position, created_at, updated_at) "
            "VALUES (:id, :user_id, 'RT2 Novel', '', '', 'en', '', "
            "        'three_act', '', '', false, "
            "        :series_id, :position, now(), now())"
        ),
        {
            "id": str(novel_id),
            "user_id": str(user_id),
            "series_id": str(series_id),
            "position": position,
        },
    )


# ---------------------------------------------------------------------------
# The regression scenario
# ---------------------------------------------------------------------------


class TestSeriesDeleteDataSafety:
    """C2: deleting a series preserves Novel-Overlay KB rows (SET NULL fate)."""

    async def test_delete_series_preserves_overlay_kb_and_drops_canon(
        self, db_session: AsyncSession
    ) -> None:
        import uuid as _uuid

        user_id = _uuid.uuid4()
        series_id = _uuid.uuid4()
        novel_id = _uuid.uuid4()

        # 1. Seed series S, novel N as a member of S, plus the owning user.
        await _seed_user(db_session, user_id)
        await _seed_series(db_session, series_id=series_id, user_id=user_id)
        await _seed_novel_member(
            db_session,
            novel_id=novel_id,
            user_id=user_id,
            series_id=series_id,
            position=1,
        )
        await db_session.flush()

        # Wire real repositories bound to the per-test transactional session.
        kb_repo = KBRepository(db_session)
        series_repo = SeriesRepository(db_session)
        series_service = SeriesService(series_repo)

        # 2. KB entry E on N — overlay scope (novel_id set, series_id NULL per D6).
        entry_e = await kb_repo.create(
            KBEntry(
                novel_id=novel_id,
                entity_type="system",
                name="Magic System",
                slug="magic",
                status="draft",
                body="Soft magic.",
            )
        )

        # 3. Canon KB entry C on S — (novel_id=NULL, series_id=S). The scope-
        # invariant CHECK allows this row. delete_canon_for_series must remove
        # it before the series row goes away.
        canon_c = await kb_repo.create(
            KBEntry(
                novel_id=None,
                series_id=series_id,
                entity_type="concept",
                name="World Law",
                slug="world-law",
                status="canon",
                body="Series-level canon entry.",
            )
        )

        # 4. Standalone entry O on N — unrelated slug, never tied to the series.
        # Its survival proves the delete doesn't nuke the novel's whole KB.
        entry_o = await kb_repo.create(
            KBEntry(
                novel_id=novel_id,
                entity_type="character",
                name="Hero",
                slug="hero",
                status="draft",
                body="Protagonist.",
            )
        )
        await db_session.flush()

        # 5. Round-trip E through the scope-mutation flow: promote to Canon,
        # then demote back to Overlay on N. This is the regression path for
        # the MissingGreenlet crash — both methods must _flush_and_refresh so
        # the ORM→Core converter can read updated_at without a sync lazy-load
        # under AsyncSession. Final state of E is unchanged (overlay on N),
        # so the C2 cascade assertions below stay valid.
        await kb_repo.promote_to_canon(novel_id, entry_e.id)
        await kb_repo.demote_to_overlay(series_id, entry_e.id, novel_id)
        await db_session.flush()

        # Sanity pre-conditions before the delete.
        assert await _novel_series_id(db_session, novel_id) == series_id
        assert await _settings_count(db_session, series_id) == 1
        assert await _canon_count(db_session, series_id) == 1

        # 5. Delete series S via the service (the entry point users hit).
        await series_service.delete_series(series_id, user_id)
        await db_session.flush()

        # 6. Novel N survives as standalone (novels.series_id SET NULL via FK).
        assert await _novel_exists(db_session, novel_id), "novel N must survive the series delete"
        assert await _novel_series_id(db_session, novel_id) is None, (
            "novels.series_id must be SET NULL by the FK, not CASCADE-delete the novel"
        )

        # 7. N's overlay row for E survives with series_id NULL.
        e_row = await _kb_row(db_session, entry_e.id)
        assert e_row is not None, (
            "overlay KB row E must survive (SET NULL on kb_entries.series_id, not CASCADE)"
        )
        assert e_row["novel_id"] == novel_id
        assert e_row["series_id"] is None, "overlay must keep series_id NULL (D6)"

        # 8. N's standalone KB entry (unrelated to the series) is intact.
        o_row = await _kb_row(db_session, entry_o.id)
        assert o_row is not None, "unrelated standalone KB entry must be untouched"
        assert o_row["novel_id"] == novel_id

        # 9. Canon rows of S are gone (delete_canon_for_series in-tx; the scope
        # invariant would forbid a Canon row whose series vanished anyway).
        assert await _canon_count(db_session, series_id) == 0, (
            "Canon rows of S must be removed (no series to belong to)"
        )
        c_row = await _kb_row(db_session, canon_c.id)
        assert c_row is None, "Canon entry C must be deleted in-transaction"

        # 10. series_settings of S are gone (CASCADE FK on series_settings).
        assert await _settings_count(db_session, series_id) == 0, (
            "series_settings must CASCADE-delete with the series"
        )

        # 11. The series itself is gone.
        assert await _series_exists(db_session, series_id) is False


# ---------------------------------------------------------------------------
# Read-only assertions (raw SQL → always reflects in-transaction state)
# ---------------------------------------------------------------------------


async def _series_exists(db_session: AsyncSession, series_id: uuid.UUID) -> bool:
    r = await db_session.execute(
        sqlalchemy.text("SELECT 1 FROM series WHERE id = :id"), {"id": str(series_id)}
    )
    return r.one_or_none() is not None


async def _novel_exists(db_session: AsyncSession, novel_id: uuid.UUID) -> bool:
    r = await db_session.execute(
        sqlalchemy.text("SELECT 1 FROM novels WHERE id = :id"), {"id": str(novel_id)}
    )
    return r.one_or_none() is not None


async def _novel_series_id(db_session: AsyncSession, novel_id: uuid.UUID) -> uuid.UUID | None:
    r = await db_session.execute(
        sqlalchemy.text("SELECT series_id FROM novels WHERE id = :id"),
        {"id": str(novel_id)},
    )
    row = r.one_or_none()
    return row[0] if row is not None else None


async def _kb_row(db_session: AsyncSession, entry_id: uuid.UUID) -> dict[str, object] | None:
    r = await db_session.execute(
        sqlalchemy.text("SELECT id, novel_id, series_id, slug FROM kb_entries WHERE id = :id"),
        {"id": str(entry_id)},
    )
    row = r.one_or_none()
    if row is None:
        return None
    return {"id": row[0], "novel_id": row[1], "series_id": row[2], "slug": row[3]}


async def _canon_count(db_session: AsyncSession, series_id: uuid.UUID) -> int:
    r = await db_session.execute(
        sqlalchemy.text(
            "SELECT COUNT(*) FROM kb_entries WHERE novel_id IS NULL AND series_id = :id"
        ),
        {"id": str(series_id)},
    )
    return int(r.scalar_one())


async def _settings_count(db_session: AsyncSession, series_id: uuid.UUID) -> int:
    r = await db_session.execute(
        sqlalchemy.text("SELECT COUNT(*) FROM series_settings WHERE series_id = :id"),
        {"id": str(series_id)},
    )
    return int(r.scalar_one())
