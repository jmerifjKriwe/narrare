"""Shared helpers for the bulk extraction API integration tests.

One helper module so ``test_bulk_extraction_api.py`` stays under the
RULE-04 hard limit; mirrors ``tests/unit/api/kb/bulk_extraction/_runner_fakes.py``
(underscore-prefixed, import-only helpers — no tests here). The fixtures
consuming these helpers live in ``tests/integration/kb/conftest.py``.

The dispatcher fake sits at the plan's DI seam: tests override
``narrare.kb.bulk_extraction.dependencies.get_bulk_dispatcher`` with it so
job state is driven via ``registry.mark_*`` without launching the AI runner.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from narrare.chapters.models import Chapter
from narrare_core.agents.extraction_types import ExtractionItem, ExtractionOutput

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


class NoopDispatcher:
    """``BulkExtractionDispatcher`` stand-in: records, never launches a runner."""

    def __init__(self) -> None:
        self.dispatched: list[tuple[str, UUID, UUID]] = []

    async def dispatch(self, job_id: str, novel_id: UUID, owner_id: UUID) -> None:
        self.dispatched.append((job_id, novel_id, owner_id))


async def register_user(client: AsyncClient) -> dict[str, str]:
    """Register a user and return auth headers."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"bulk-extract-{uuid4().hex[:10]}@example.com",
            "password": "testpassword123",
            "display_name": "Bulk Extraction Test User",
        },
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def create_novel(client: AsyncClient, headers: dict[str, str], title: str) -> UUID:
    """Create a novel for the authenticated user and return its id."""
    resp = await client.post(
        "/api/v1/novels", json={"title": title, "language": "en"}, headers=headers
    )
    assert resp.status_code == 201
    return UUID(resp.json()["id"])


async def add_chapters(db_session: AsyncSession, novel_id: UUID, count: int = 3) -> list[UUID]:
    """Persist ``count`` contentful chapters (position order) for ``novel_id``."""
    chapters = [
        Chapter(
            novel_id=novel_id,
            title=f"Chapter {index + 1}",
            content=f"Content of chapter {index + 1}: Elena crossed the harbor at dawn.",
            position=index,
        )
        for index in range(count)
    ]
    db_session.add_all(chapters)
    await db_session.flush()
    return [chapter.id for chapter in chapters]


def output(n_items: int) -> ExtractionOutput:
    """A minimal valid ``ExtractionOutput`` with ``n_items`` results."""
    return ExtractionOutput(
        results=[
            ExtractionItem(
                item_type="new_entity", name=f"item-{i}", confidence=0.9, source_text="s"
            )
            for i in range(n_items)
        ],
    )
