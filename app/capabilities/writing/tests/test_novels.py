"""Novels against the real database."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.main import app
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")


async def test_create_then_list_novel() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/writing/novels", json={"title": "Der Nebel"})
        assert created.status_code == 201
        assert created.json()["title"] == "Der Nebel"

        listed = await client.get("/api/writing/novels")
        assert listed.status_code == 200
        assert [novel["title"] for novel in listed.json()] == ["Der Nebel"]


async def test_create_persists_genre_and_blurb() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/writing/novels",
            json={
                "title": "Der Nebel",
                "genre": "Mystery",
                "blurb": "A fog rolls in from the sea and does not leave.",
            },
        )
        assert created.status_code == 201
        body = created.json()
        assert body["genre"] == "Mystery"
        assert body["blurb"] == "A fog rolls in from the sea and does not leave."
        # The timestamp the start page orders by; timezone-aware end to end.
        assert datetime.fromisoformat(body["updated_at"]).tzinfo is not None

        fetched = await client.get(f"/api/writing/novels/{body['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["genre"] == "Mystery"
        assert fetched.json()["blurb"] == "A fog rolls in from the sea and does not leave."
        assert fetched.json()["updated_at"] == body["updated_at"]


async def test_create_without_metadata_leaves_it_null() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/writing/novels", json={"title": "Der Nebel"})
        assert created.status_code == 201
        assert created.json()["genre"] is None
        assert created.json()["blurb"] is None


async def test_another_users_novel_is_not_listed() -> None:
    await seed_user(OTHER_USER)
    async with Session() as session:
        await session.execute(
            text(
                "INSERT INTO novels (id, user_id, title, created_at, updated_at) "
                "VALUES (:id, :user_id, :title, now(), now())"
            ),
            {"id": uuid4(), "user_id": OTHER_USER, "title": "Fremd"},
        )
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = await client.get("/api/writing/novels")
        assert listed.json() == []


async def test_get_novel_returns_the_novel() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/writing/novels", json={"title": "Der Nebel"})
        novel_id = created.json()["id"]

        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        assert fetched.status_code == 200
        assert fetched.json()["title"] == "Der Nebel"


async def test_another_users_novel_is_not_found() -> None:
    novel_id = uuid4()
    await seed_user(OTHER_USER)
    async with Session() as session:
        await session.execute(
            text(
                "INSERT INTO novels (id, user_id, title, created_at, updated_at) "
                "VALUES (:id, :user_id, :title, now(), now())"
            ),
            {"id": novel_id, "user_id": OTHER_USER, "title": "Fremd"},
        )
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        assert fetched.status_code == 404
