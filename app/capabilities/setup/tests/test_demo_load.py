"""Setup with a demo loads the archive through the engine; without one, the
blank first run is exactly what it was before the demos existed.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.api.main import app
from app.capabilities.setup.service import SetupService
from app.kernel.contracts.models import Chapter, Entity, EntityRelation, Novel
from app.kernel.db.session import Session

pytestmark = pytest.mark.timeout(60)


@pytest.fixture(autouse=True)
def fake_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    """The demo import embeds every entity it births through the env-selected
    provider; no test here may reach a network, so the fake is pinned."""
    monkeypatch.setenv("NARRE_EMBEDDING_PROVIDER", "fake")


async def test_complete_with_demo_loads_archive() -> None:
    async with Session() as session:
        novel = await SetupService(session).complete("ignored for a demo", demo="dead-signal")

    async with Session() as session:
        stored = await session.get(Novel, novel.id)
        assert stored is not None
        # the archive's metadata wins: the demo carries its own identity
        assert stored.title == "Dead Signal"
        assert stored.author == "Narrare Demo"
        assert stored.genre == "Science Fiction"
        assert stored.language == "en"
        chapters = (
            await session.scalars(select(Chapter).where(Chapter.novel_id == novel.id))
        ).all()
        assert len(chapters) == 3
        entities = (await session.scalars(select(Entity).where(Entity.novel_id == novel.id))).all()
        assert len(entities) == 8
        relations = (await session.scalars(select(EntityRelation))).all()
        assert len(relations) == 3
        assert all(relation.relation_type == "related_to" for relation in relations)
        by_name = {entity.name: entity for entity in entities}
        maya_to_aria = [
            relation
            for relation in relations
            if relation.from_entity_id == by_name["Dr. Maya Chen"].id
            and relation.to_entity_id
            == by_name["ARIA (Autonomous Response and Intelligence Algorithm)"].id
        ]
        assert len(maya_to_aria) == 1
        assert maya_to_aria[0].note is not None
        assert maya_to_aria[0].note.startswith("Complex partnership with ARIA")


async def test_complete_without_demo_is_unchanged() -> None:
    async with Session() as session:
        novel = await SetupService(session).complete("Der Nebel")

    async with Session() as session:
        stored = await session.get(Novel, novel.id)
        assert stored is not None
        assert stored.title == "Der Nebel"
        assert stored.author is None and stored.language is None
        novels = (await session.scalars(select(Novel))).all()
        assert len(novels) == 1
        assert await session.scalar(select(func.count()).select_from(Chapter)) == 0
        assert await session.scalar(select(func.count()).select_from(Entity)) == 0
        assert await session.scalar(select(func.count()).select_from(EntityRelation)) == 0


async def test_unknown_demo_slug_is_422() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/setup", json={"novel_title": "Der Nebel", "demo": "no-such-demo"}
        )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(entry.get("loc") == ["body", "demo"] for entry in detail)
    async with Session() as session:
        assert await session.scalar(select(func.count()).select_from(Novel)) == 0
