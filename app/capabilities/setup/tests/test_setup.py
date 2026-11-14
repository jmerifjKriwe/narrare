"""First run against the real database: empty, then installed, then closed."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.api.main import app
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Novel, User
from app.kernel.db.session import Session

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


async def test_setup_stores_the_wizard_settings() -> None:
    payload = {
        "novel_title": "Der Nebel",
        "genre": "Literary",
        "target_words": 65000,
        "author_typology": "plantser",
        "dramatic_form": "three-act",
        "ai_role": "lektor",
        "canon_strictness": 4,
    }
    async with _client() as client:
        completed = await client.post("/api/setup", json=payload)
        assert completed.status_code == 201
        novel_id = completed.json()["novel_id"]

    async with Session() as session:
        stored = await session.get(Novel, novel_id)
        assert stored is not None
        assert stored.genre == "Literary"
        assert stored.target_words == 65000
        assert stored.author_typology == "plantser"
        assert stored.dramatic_form == "three-act"
        assert stored.ai_role == "lektor"
        assert stored.canon_strictness == 4


async def test_setup_settings_are_optional() -> None:
    async with _client() as client:
        completed = await client.post("/api/setup", json={"novel_title": "Der Nebel"})
        assert completed.status_code == 201
        novel_id = completed.json()["novel_id"]

    async with Session() as session:
        stored = await session.get(Novel, novel_id)
        assert stored is not None
        assert stored.genre is None
        assert stored.target_words is None
        assert stored.author_typology is None
        assert stored.dramatic_form is None
        assert stored.ai_role is None
        assert stored.canon_strictness is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("target_words", 0),
        ("target_words", -5),
        # One past the Integer column's ceiling: must be a 422, not a DB overflow.
        ("target_words", 2_147_483_648),
        ("author_typology", "bogus"),
        ("ai_role", "bogus"),
        ("canon_strictness", 0),
        ("canon_strictness", 6),
    ],
)
async def test_setup_rejects_invalid_settings(field: str, value: object) -> None:
    async with _client() as client:
        response = await client.post("/api/setup", json={"novel_title": "Der Nebel", field: value})
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any(entry.get("loc") == ["body", field] for entry in detail)

    async with Session() as session:
        assert await session.scalar(select(func.count()).select_from(Novel)) == 0


async def test_setup_accepts_the_largest_word_goal_the_column_holds() -> None:
    async with _client() as client:
        completed = await client.post(
            "/api/setup", json={"novel_title": "Der Nebel", "target_words": 2_147_483_647}
        )
        assert completed.status_code == 201
        novel_id = completed.json()["novel_id"]

    async with Session() as session:
        stored = await session.get(Novel, novel_id)
        assert stored is not None
        assert stored.target_words == 2_147_483_647
