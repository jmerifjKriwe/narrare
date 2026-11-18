"""The series HTTP door (W4 Task 19): create and list, user-owned.

The book-settings surface creates a series inline and links the book to
it; the select reads the user's own series. The create trims like a novel
title and refuses a whitespace-only name by field; the list never carries
another user's row.
"""

from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.api.main import app
from app.capabilities.writing.repository import SeriesRepository
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import User
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_a_series_is_created_for_the_current_user() -> None:
    async with _client() as client:
        created = await client.post("/api/writing/series", json={"title": "Tiefsee-Chroniken"})
        assert created.status_code == 201
        body = created.json()
        assert body["title"] == "Tiefsee-Chroniken"
        assert body["created_at"] is not None

    # The row belongs to the user the request rode as — rule 4.
    async with Session() as session:
        stored = await SeriesRepository(session, LOCAL_USER_ID).get(UUID(body["id"]))
        assert stored is not None
        assert stored.user_id == LOCAL_USER_ID


async def test_the_title_is_trimmed_like_a_books() -> None:
    async with _client() as client:
        created = await client.post(
            "/api/writing/series", json={"title": "  Die Nebel-Chroniken  "}
        )
        assert created.status_code == 201
        assert created.json()["title"] == "Die Nebel-Chroniken"


@pytest.mark.parametrize("title", ["", "   ", "\t\n"])
async def test_a_nameless_series_is_refused_by_field(title: str) -> None:
    async with _client() as client:
        refused = await client.post("/api/writing/series", json={"title": title})
        assert refused.status_code == 422
        assert any(entry["loc"] == ["body", "title"] for entry in refused.json()["detail"])


async def test_an_over_long_title_is_refused() -> None:
    async with _client() as client:
        refused = await client.post("/api/writing/series", json={"title": "x" * 201})
        assert refused.status_code == 422


async def test_the_list_carries_only_the_users_own_series() -> None:
    await seed_user(OTHER_USER)
    async with Session() as session:
        await SeriesRepository(session, OTHER_USER).create("Fremde Reihe")
        await session.commit()

    async with _client() as client:
        for title in ("Tiefsee-Chroniken", "Erebus-Expeditionen"):
            created = await client.post("/api/writing/series", json={"title": title})
            assert created.status_code == 201
        listed = await client.get("/api/writing/series")
        assert listed.status_code == 200
        # Alphabetical — the select's order, never another user's row.
        assert [row["title"] for row in listed.json()] == [
            "Erebus-Expeditionen",
            "Tiefsee-Chroniken",
        ]


async def test_an_empty_atelier_lists_no_series() -> None:
    async with _client() as client:
        listed = await client.get("/api/writing/series")
        assert listed.status_code == 200
        assert listed.json() == []


async def test_creating_a_series_before_setup_is_refused() -> None:
    async with Session() as session:
        await session.execute(delete(User).where(User.id == LOCAL_USER_ID))
        await session.commit()

    async with _client() as client:
        refused = await client.post("/api/writing/series", json={"title": "Zu früh"})
        assert refused.status_code == 409
        assert refused.json()["detail"] == "setup required"


async def test_a_duplicate_series_name_is_refused_per_user() -> None:
    """The contract (review fix): one atelier, one series per name — the
    settings select resolves the book's link by title, so a duplicate
    would make that resolution ambiguous. The trimmed name is the name."""
    async with _client() as client:
        first = await client.post("/api/writing/series", json={"title": "Tiefsee-Chroniken"})
        assert first.status_code == 201
        again = await client.post("/api/writing/series", json={"title": "Tiefsee-Chroniken"})
        assert again.status_code == 409
        padded = await client.post("/api/writing/series", json={"title": "  Tiefsee-Chroniken  "})
        assert padded.status_code == 409
        listed = await client.get("/api/writing/series")
        assert [row["title"] for row in listed.json()] == ["Tiefsee-Chroniken"]


async def test_another_user_may_carry_the_same_series_name() -> None:
    """The uniqueness is per user — two ateliers, two independent shelves."""
    await seed_user(OTHER_USER)
    async with Session() as session:
        await SeriesRepository(session, OTHER_USER).create("Tiefsee-Chroniken")
        await session.commit()

    async with _client() as client:
        created = await client.post("/api/writing/series", json={"title": "Tiefsee-Chroniken"})
        assert created.status_code == 201
