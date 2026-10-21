"""The writing capability against the real database.

The schema comes from the migration, not from metadata, so a migration that drifts
from the models fails here before it fails in production.
"""

from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from alembic import command
from app.api.main import app
from app.kernel.db.session import Session

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture(scope="session", autouse=True)
def schema() -> None:
    config = Config("app/kernel/db/alembic.ini")
    config.set_main_option("script_location", "app/kernel/db/migrations")
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
async def empty_tables() -> None:
    async with Session() as session:
        await session.execute(text("TRUNCATE novels, chapters, users CASCADE"))
        await session.commit()


async def test_create_then_list_novel() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/writing/novels", json={"title": "Der Nebel"})
        assert created.status_code == 201
        assert created.json()["title"] == "Der Nebel"

        listed = await client.get("/api/writing/novels")
        assert listed.status_code == 200
        assert [novel["title"] for novel in listed.json()] == ["Der Nebel"]


async def test_another_users_novel_is_not_listed() -> None:
    async with Session() as session:
        await session.execute(
            text(
                "INSERT INTO novels (id, user_id, title, created_at) "
                "VALUES (:id, :user_id, :title, now())"
            ),
            {"id": uuid4(), "user_id": OTHER_USER, "title": "Fremd"},
        )
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = await client.get("/api/writing/novels")
        assert listed.json() == []
