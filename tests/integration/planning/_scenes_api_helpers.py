"""Shared scene-plan API test helpers (PLAN-001).

Seed builders shared by the scene API modules (``test_scenes_api.py``
aggregate GET/PUT, ``test_scenes_ai_api.py`` AI draft/refine). The
``novel_and_chapter`` fixture is re-exported through the planning
``conftest.py`` so test modules need no fixture imports. Extracted for
the 400-line test-file limit (RULE-04).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from narrare.auth.models import User
from narrare.chapters.models import Chapter
from narrare.novels.models import Novel
from narrare.planning.models import ScenePlan

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def _create_novel_with_chapter(
    client: AsyncClient, auth_headers: dict[str, str]
) -> tuple[str, str]:
    """Create a novel with one chapter via the API; return (novel_id, chapter_id)."""
    novel_resp = await client.post(
        "/api/v1/novels",
        json={"title": "Scene Novel", "language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        json={"title": "Chapter 1", "content": "Once upon a time."},
        headers=auth_headers,
    )
    assert chapter_resp.status_code == 201
    return novel_id, chapter_resp.json()["id"]


async def _seed_scene(
    db_session: AsyncSession,
    chapter_id: str,
    position: int,
    *,
    title: str = "",
    status: str = "planned",
) -> uuid.UUID:
    """Insert one ScenePlan row directly (timestamps are DB-owned server defaults)."""
    scene_id = uuid.uuid4()
    db_session.add(
        ScenePlan(
            id=scene_id,
            chapter_id=uuid.UUID(chapter_id),
            position=position,
            title=title,
            status=status,
        )
    )
    await db_session.flush()
    return scene_id


async def _seed_foreign_users_novel(db_session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert a novel + chapter owned by a DIFFERENT user; return both ids."""
    other_user = User(
        id=uuid.uuid4(),
        email=f"other-{uuid.uuid4().hex[:12]}@example.com",
        hashed_password="not-a-real-hash",
    )
    db_session.add(other_user)
    await db_session.flush()

    novel = Novel(id=uuid.uuid4(), user_id=other_user.id, title="Foreign Novel")
    db_session.add(novel)
    await db_session.flush()

    chapter = Chapter(id=uuid.uuid4(), novel_id=novel.id, title="Foreign Chapter", position=0)
    db_session.add(chapter)
    await db_session.flush()
    return novel.id, chapter.id


@pytest.fixture
async def novel_and_chapter(client: AsyncClient, auth_headers: dict[str, str]) -> dict[str, str]:
    """One novel with a single chapter, created through the API."""
    novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)
    return {"novel_id": novel_id, "chapter_id": chapter_id}
