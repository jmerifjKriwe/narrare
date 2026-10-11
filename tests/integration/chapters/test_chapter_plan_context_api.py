"""Integration tests for the summary-only plan-context endpoint (PLAN-001 FU1 BE follow-up).

``GET /novels/{novel_id}/chapters/{chapter_id}/plan-context`` returns the
chapter plus its position-adjacent neighbors as title + summary only — the
planning surface's lighter alternative to three full-chapter GETs whose
payloads carry ``content`` (FU1 report concern).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

from narrare.chapters.models import Chapter

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def _create_novel(client: AsyncClient, auth_headers: dict[str, str]) -> str:
    response = await client.post(
        "/api/v1/novels",
        json={"title": "Plan Context Novel", "language": "en"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_chapter(
    client: AsyncClient,
    auth_headers: dict[str, str],
    novel_id: str,
    title: str,
    content: str,
) -> str:
    response = await client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        json={"title": title, "content": content},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _seed_summaries(db_session: AsyncSession, novel_id: str, summaries: list[str]) -> None:
    """Set chapter summaries in position order (0..n) for a seeded novel."""
    result = await db_session.execute(
        select(Chapter).where(Chapter.novel_id == uuid.UUID(novel_id)).order_by(Chapter.position)
    )
    chapters = list(result.scalars())
    assert len(chapters) == len(summaries)
    for chapter, summary in zip(chapters, summaries, strict=True):
        chapter.summary = summary
    await db_session.flush()


async def _second_user_headers(db_session: AsyncSession) -> dict[str, str]:
    """Auth headers for a second, distinct user (cross-user 404 test)."""
    from datetime import UTC, datetime

    from narrare._app.config import get_settings
    from narrare.auth.models import User
    from narrare.auth.security import create_access_token

    now = datetime.now(UTC)
    user = User(
        id=uuid.uuid4(),
        email=f"plan-ctx-b-{uuid.uuid4().hex[:12]}@example.com",
        hashed_password="not-a-real-hash",
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    await db_session.flush()
    settings = get_settings()
    token = create_access_token(
        subject=str(user.id),
        secret_key=settings.secret_key,
        expires_minutes=settings.access_token_expire_minutes,
    )
    return {"Authorization": f"Bearer {token}"}


class TestPlanContextHappyPath:
    async def test_middle_chapter_returns_both_neighbors_summary_only(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        novel_id = await _create_novel(client, auth_headers)
        await _create_chapter(client, auth_headers, novel_id, "First", "First prose.")
        middle_id = await _create_chapter(client, auth_headers, novel_id, "Middle", "Middle prose.")
        await _create_chapter(client, auth_headers, novel_id, "Last", "Last prose.")
        await _seed_summaries(db_session, novel_id, ["One liner.", "Two liner.", "Three."])

        response = await client.get(
            f"/api/v1/novels/{novel_id}/chapters/{middle_id}/plan-context",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert set(data) == {"chapter", "previous", "next"}
        for part in (data["chapter"], data["previous"], data["next"]):
            assert set(part) == {"title", "summary"}
            assert "content" not in part
        assert data["chapter"] == {"title": "Middle", "summary": "Two liner."}
        assert data["previous"] == {"title": "First", "summary": "One liner."}
        assert data["next"] == {"title": "Last", "summary": "Three."}


class TestPlanContextEdgeChapters:
    async def test_first_chapter_previous_is_null(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        novel_id = await _create_novel(client, auth_headers)
        first_id = await _create_chapter(client, auth_headers, novel_id, "First", "Prose.")
        await _create_chapter(client, auth_headers, novel_id, "Second", "Prose.")
        await _seed_summaries(db_session, novel_id, ["S1.", "S2."])

        response = await client.get(
            f"/api/v1/novels/{novel_id}/chapters/{first_id}/plan-context",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["previous"] is None
        assert data["chapter"] == {"title": "First", "summary": "S1."}
        assert data["next"] == {"title": "Second", "summary": "S2."}

    async def test_last_chapter_next_is_null(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        novel_id = await _create_novel(client, auth_headers)
        await _create_chapter(client, auth_headers, novel_id, "First", "Prose.")
        last_id = await _create_chapter(client, auth_headers, novel_id, "Last", "Prose.")
        await _seed_summaries(db_session, novel_id, ["S1.", "S2."])

        response = await client.get(
            f"/api/v1/novels/{novel_id}/chapters/{last_id}/plan-context",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["previous"] == {"title": "First", "summary": "S1."}
        assert data["next"] is None


class TestPlanContextErrors:
    async def test_unknown_chapter_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        novel_id = await _create_novel(client, auth_headers)
        response = await client.get(
            f"/api/v1/novels/{novel_id}/chapters/{uuid.uuid4()}/plan-context",
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_chapter_of_other_novel_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        novel_a = await _create_novel(client, auth_headers)
        novel_b = await _create_novel(client, auth_headers)
        chapter_b = await _create_chapter(client, auth_headers, novel_b, "In B", "Prose.")

        response = await client.get(
            f"/api/v1/novels/{novel_a}/chapters/{chapter_b}/plan-context",
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_foreign_user_returns_404_like_unknown(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        novel_id = await _create_novel(client, auth_headers)
        chapter_id = await _create_chapter(client, auth_headers, novel_id, "Mine", "Prose.")
        foreign_headers = await _second_user_headers(db_session)

        response = await client.get(
            f"/api/v1/novels/{novel_id}/chapters/{chapter_id}/plan-context",
            headers=foreign_headers,
        )
        assert response.status_code == 404
        # Anti-enumeration parity: foreign ≡ unknown (same body shape, same code).
        unknown = await client.get(
            f"/api/v1/novels/{novel_id}/chapters/{uuid.uuid4()}/plan-context",
            headers=foreign_headers,
        )
        assert unknown.status_code == 404
        assert set(response.json()) == set(unknown.json()) == {"detail", "code"}
        assert response.json()["code"] == unknown.json()["code"] == "NOT_FOUND"
