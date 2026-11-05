"""Editing a novel's metadata: PATCH changes only the fields the body carries."""

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


async def _novel_id(client: AsyncClient, **metadata: str) -> str:
    """A created novel's id — titled "Der Nebel", plus the metadata passed."""
    created = await client.post("/api/writing/novels", json={"title": "Der Nebel", **metadata})
    assert created.status_code == 201
    return created.json()["id"]


async def test_patch_changes_only_the_fields_sent() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client, genre="Mystery", blurb="A fog rolls in.")
        patched = await client.patch(
            f"/api/writing/novels/{novel_id}", json={"author": "J. Autorin"}
        )
        assert patched.status_code == 200
        body = patched.json()
        assert body["author"] == "J. Autorin"
        # the fields the body does not carry are untouched
        assert body["title"] == "Der Nebel"
        assert body["genre"] == "Mystery"
        assert body["blurb"] == "A fog rolls in."
        assert body["language"] is None


async def test_patch_trims_the_title() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client)
        patched = await client.patch(
            f"/api/writing/novels/{novel_id}", json={"title": "  Die Stadt  "}
        )
        assert patched.status_code == 200
        assert patched.json()["title"] == "Die Stadt"


async def test_patch_refuses_an_empty_title() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client)
        for title in ("", "   "):
            refused = await client.patch(f"/api/writing/novels/{novel_id}", json={"title": title})
            assert refused.status_code == 422, title
            assert refused.json()["detail"] == "invalid title"
        # the refusals wrote nothing
        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        assert fetched.json()["title"] == "Der Nebel"


async def test_patch_refuses_a_bad_language_code() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client)
        for code in ("deutsch", "d", "DE", "en_GB"):
            refused = await client.patch(f"/api/writing/novels/{novel_id}", json={"language": code})
            assert refused.status_code == 422, code
            assert refused.json()["detail"] == "invalid language"
        # the refusals wrote nothing
        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        assert fetched.json()["language"] is None


async def test_patch_clears_the_language_with_null_and_with_empty_string() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client)
        chose = await client.patch(f"/api/writing/novels/{novel_id}", json={"language": "de"})
        assert chose.status_code == 200
        assert chose.json()["language"] == "de"

        # null is a value, not an absence: the language clears
        nulled = await client.patch(f"/api/writing/novels/{novel_id}", json={"language": None})
        assert nulled.status_code == 200
        assert nulled.json()["language"] is None

        chose_again = await client.patch(f"/api/writing/novels/{novel_id}", json={"language": "en"})
        assert chose_again.status_code == 200
        assert chose_again.json()["language"] == "en"

        # the empty string clears too — same honest no-answer
        emptied = await client.patch(f"/api/writing/novels/{novel_id}", json={"language": ""})
        assert emptied.status_code == 200
        assert emptied.json()["language"] is None


async def test_patch_accepts_bcp47_like_codes() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client)
        for code in ("de", "en-GB"):
            patched = await client.patch(f"/api/writing/novels/{novel_id}", json={"language": code})
            assert patched.status_code == 200, code
            assert patched.json()["language"] == code


async def test_patch_refuses_a_genre_over_80() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client)
        refused = await client.patch(f"/api/writing/novels/{novel_id}", json={"genre": "x" * 81})
        assert refused.status_code == 422
        assert refused.json()["detail"] == "invalid genre"
        # the refusal wrote nothing
        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        assert fetched.json()["genre"] is None


async def test_patch_bumps_updated_at() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client)
        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        before = datetime.fromisoformat(fetched.json()["updated_at"])
        patched = await client.patch(
            f"/api/writing/novels/{novel_id}", json={"author": "J. Autorin"}
        )
        assert patched.status_code == 200
        after = datetime.fromisoformat(patched.json()["updated_at"])
        assert after > before


async def test_patch_answers_404_for_a_foreign_novel() -> None:
    await seed_user(OTHER_USER)
    foreign_id = uuid4()
    async with Session() as session:
        await session.execute(
            text(
                "INSERT INTO novels (id, user_id, title, created_at, updated_at) "
                "VALUES (:id, :user_id, :title, now(), now())"
            ),
            {"id": foreign_id, "user_id": OTHER_USER, "title": "Fremd"},
        )
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        patched = await client.patch(
            f"/api/writing/novels/{foreign_id}", json={"title": "Umgetauft"}
        )
        assert patched.status_code == 404
        assert patched.json()["detail"] == "novel not found"
