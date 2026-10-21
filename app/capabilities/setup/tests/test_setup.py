"""First run against the real database: empty, then installed, then closed."""

import pytest
from app.api.main import app
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Novel, User
from app.kernel.db.session import Session
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

pytestmark = pytest.mark.timeout(60)


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_a_fresh_instance_is_not_set_up() -> None:
    async with _client() as client:
        response = await client.get("/api/setup/status")
        assert response.status_code == 200
        assert response.json() == {"complete": False}


async def test_setup_creates_the_local_user_and_the_first_novel() -> None:
    async with _client() as client:
        completed = await client.post("/api/setup", json={"novel_title": "Der Nebel"})
        assert completed.status_code == 201
        assert completed.json()["novel_title"] == "Der Nebel"

        assert (await client.get("/api/setup/status")).json() == {"complete": True}

    async with Session() as session:
        assert await session.get(User, LOCAL_USER_ID) is not None
        novels = (await session.scalars(select(Novel).where(Novel.user_id == LOCAL_USER_ID))).all()
        assert [novel.title for novel in novels] == ["Der Nebel"]


async def test_setup_runs_only_once() -> None:
    async with _client() as client:
        assert (
            await client.post("/api/setup", json={"novel_title": "Der Nebel"})
        ).status_code == 201

        again = await client.post("/api/setup", json={"novel_title": "Zweiter"})
        assert again.status_code == 409

    async with Session() as session:
        count = await session.scalar(select(func.count()).select_from(Novel))
        assert count == 1
