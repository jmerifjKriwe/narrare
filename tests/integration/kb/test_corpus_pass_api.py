"""Integration tests for the corpus pass API (F3 T2, spec §4.3/§4.4).

Real endpoints over the REAL ``BulkExtractionService`` + REAL in-memory
registry + REAL ``RepositoryCorpusSource`` (``ChapterRepository.list_by_novel``,
position order) — only the dispatcher is overridden (a recording no-op) so
tests drive job state via ``registry.mark_*`` without launching the AI
runner (the F2-prescribed DI-seam bypass).

Covers the plan T2 Step-5 list: the honest capped estimate over a
150-chapter novel, start (201) over the START-time prefix with the default
un-analyzed dedup block on status, the explicit-job ``dedup: null``
invariant, owner gating (foreign ≡ unknown → 404 on BOTH routes), and the
empty-prefix 422s (zero-chapter novel — rider b; oversized first chapter —
rider c, split-first guidance).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from narrare.chapters.models import Chapter
from tests.integration.kb._bulk_extraction_helpers import (
    NoopDispatcher,
    create_novel,
    register_user,
)

if TYPE_CHECKING:
    from uuid import UUID

    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

#: The bulk registry is process-global — sweep it around every test here.
pytestmark = pytest.mark.usefixtures("clean_bulk_registry")

ESTIMATE_URL = "/api/v1/novels/{novel_id}/kb/extract/bulk/corpus/estimate"
START_URL = "/api/v1/novels/{novel_id}/kb/extract/bulk/corpus"


async def _add_worded_chapters(
    db_session: AsyncSession, novel_id: UUID, count: int, words_each: int
) -> list[UUID]:
    """Persist ``count`` chapters with an explicit ``word_count`` (position order).

    The word-count COLUMN is the SSOT for the D20a cap math (the corpus
    source enumerates rows, not content), so fixtures set it directly and
    keep the content short — a 250k-word prose fixture would be pure waste.
    """
    chapters = [
        Chapter(
            novel_id=novel_id,
            title=f"Chapter {index + 1}",
            content=f"Content of chapter {index + 1}: Elena crossed the harbor at dawn.",
            position=index,
            word_count=words_each,
        )
        for index in range(count)
    ]
    db_session.add_all(chapters)
    await db_session.flush()
    return [chapter.id for chapter in chapters]


async def test_estimate_reports_honest_capped_numbers(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    novel_id = await create_novel(client, auth_headers, "Capped Corpus Novel")
    await _add_worded_chapters(db_session, novel_id, count=150, words_each=1_000)

    resp = await client.get(ESTIMATE_URL.format(novel_id=novel_id), headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_chapters"] == 150
    assert body["total_word_count"] == 150_000
    assert body["chapter_count"] == 120
    assert body["word_count"] == 120_000
    assert body["ai_calls"] == 120  # D14a: one call per chapter
    assert body["capped"] is True
    assert body["cap_reason"] == "chapters"
    assert len(body["selected_chapter_ids"]) == 120  # ids verified by the start test below


async def test_start_creates_corpus_job_over_the_start_time_prefix(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    bulk_dispatcher: NoopDispatcher,
) -> None:
    novel_id = await create_novel(client, auth_headers, "Corpus Start Novel")
    chapter_ids = await _add_worded_chapters(db_session, novel_id, count=150, words_each=1_000)

    start = await client.post(START_URL.format(novel_id=novel_id), headers=auth_headers)

    assert start.status_code == 201
    job = start.json()
    assert job["novel_id"] == str(novel_id)
    assert job["status"] == "pending"
    assert job["totals"] == {"total": 120, "done": 0, "failed": 0, "remaining": 120}
    assert len(bulk_dispatcher.dispatched) == 1  # the runner was dispatched

    status = await client.get(
        f"/api/v1/novels/{novel_id}/kb/extract/bulk/{job['job_id']}/status",
        headers=auth_headers,
    )
    assert status.status_code == 200
    body = status.json()
    # The START-time prefix: the first 120 chapters in position order …
    assert [row["position"] for row in body["chapters"]] == list(range(120))
    assert [row["chapter_id"] for row in body["chapters"]] == [
        str(cid) for cid in chapter_ids[:120]
    ]
    assert all(row["state"] == "pending" for row in body["chapters"])
    # … with the corpus default dedup block (not yet analyzed — invariant 3).
    assert body["dedup"] == {"analyzed": False, "suggestion_count": None}


async def test_explicit_job_status_has_no_dedup_block(
    client: AsyncClient,
    auth_headers: dict[str, str],
    bulk_novel_id: UUID,
    bulk_chapter_ids: list[UUID],
    bulk_dispatcher: NoopDispatcher,
) -> None:
    start = await client.post(
        f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk",
        json={"chapter_ids": [str(cid) for cid in bulk_chapter_ids]},
        headers=auth_headers,
    )
    assert start.status_code == 201

    status = await client.get(
        f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk/{start.json()['job_id']}/status",
        headers=auth_headers,
    )

    assert status.status_code == 200
    assert status.json()["dedup"] is None  # invariant 3: explicit jobs never trigger


async def test_corpus_routes_are_owner_gated(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    novel_id = await create_novel(client, auth_headers, "Gated Corpus Novel")
    await _add_worded_chapters(db_session, novel_id, count=2, words_each=1_000)
    foreign_headers = await register_user(client)

    estimate = await client.get(ESTIMATE_URL.format(novel_id=novel_id), headers=foreign_headers)
    start = await client.post(START_URL.format(novel_id=novel_id), headers=foreign_headers)

    assert estimate.status_code == 404  # foreign ≡ unknown (anti-enumeration)
    assert start.status_code == 404


async def test_estimate_for_zero_chapter_novel_is_honest_zero(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    novel_id = await create_novel(client, auth_headers, "Empty Novel")

    resp = await client.get(ESTIMATE_URL.format(novel_id=novel_id), headers=auth_headers)

    assert resp.status_code == 200  # rider b: the estimate is an HONEST zero
    body = resp.json()
    assert body["total_chapters"] == 0
    assert body["total_word_count"] == 0
    assert body["selected_chapter_ids"] == []
    assert body["chapter_count"] == 0
    assert body["word_count"] == 0
    assert body["ai_calls"] == 0
    assert body["capped"] is False
    assert body["cap_reason"] is None


async def test_start_for_zero_chapter_novel_is_422(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    novel_id = await create_novel(client, auth_headers, "Empty Start Novel")

    resp = await client.post(START_URL.format(novel_id=novel_id), headers=auth_headers)

    assert resp.status_code == 422  # rider b: START never runs nothing silently
    assert "0 chapters" in resp.json()["detail"]


async def test_start_with_oversized_first_chapter_is_422(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    novel_id = await create_novel(client, auth_headers, "Oversized First Novel")
    await _add_worded_chapters(db_session, novel_id, count=1, words_each=250_000)

    resp = await client.post(START_URL.format(novel_id=novel_id), headers=auth_headers)

    assert resp.status_code == 422  # rider c: ValidationError → the global 422 mapping
    detail = resp.json()["detail"]
    assert "250000" in detail  # honest counts
    assert "200000" in detail
    assert "Split" in detail  # split-first guidance
