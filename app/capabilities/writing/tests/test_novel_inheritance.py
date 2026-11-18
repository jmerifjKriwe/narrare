"""A new book inherits the atelier's answers (the dialog note's truth).

The new-book dialog promises that dramaturgy, AI role and canon strictness
come from the atelier's settings. The honest source is the instance's first
book — the one setup created in the same transaction as the user, the oldest
``created_at`` of the user's novels. ``create_novel`` reads it once and copies
the four wizard columns onto the new row; the source is never written. A
column without an answer stays without one — no guessed default, and a book
created where no source exists carries NULLs, the honest no-answer.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Novel
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")

# One of each settings vocabulary — the setup wizard's own answers.
ATELIER_ANSWERS = {
    "author_typology": "plantser",
    "dramatic_form": "three-act",
    "ai_role": "lektor",
    "canon_strictness": 3,
}


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _create_novel(client: AsyncClient, title: str) -> str:
    response = await client.post("/api/writing/novels", json={"title": title})
    assert response.status_code == 201
    return response.json()["id"]


async def _write_answers(novel_id: str, **answers: object) -> None:
    """The wizard's answers, written the way the wizard writes them: on the
    row itself (the setup capability owns that door)."""
    async with Session() as session:
        novel = await session.get(Novel, UUID(novel_id))
        assert novel is not None
        for field, value in answers.items():
            setattr(novel, field, value)
        await session.commit()


async def _stored_answers(novel_id: str) -> tuple[object, ...]:
    """The four wizard columns where they live — the read response carries
    none of them, so the row itself is the honest check."""
    async with Session() as session:
        novel = await session.get(Novel, UUID(novel_id))
        assert novel is not None
        return (
            novel.author_typology,
            novel.dramatic_form,
            novel.ai_role,
            novel.canon_strictness,
        )


async def test_a_new_book_inherits_the_ateliers_answers() -> None:
    async with _client() as client:
        first_id = await _create_novel(client, "Das Atelier-Buch")
        await _write_answers(first_id, **ATELIER_ANSWERS)

        new_id = await _create_novel(client, "Die Prüferin")

    assert await _stored_answers(new_id) == (
        ATELIER_ANSWERS["author_typology"],
        ATELIER_ANSWERS["dramatic_form"],
        ATELIER_ANSWERS["ai_role"],
        ATELIER_ANSWERS["canon_strictness"],
    )


async def test_no_answer_stays_no_answer() -> None:
    """The first book carries NULLs (setup's blank path without answers):
    the new book inherits the absence, not a guessed default."""
    async with _client() as client:
        await _create_novel(client, "Das Atelier-Buch")
        new_id = await _create_novel(client, "Die Prüferin")

    assert await _stored_answers(new_id) == (None, None, None, None)


async def test_a_partial_answer_copies_column_by_column() -> None:
    """Each column rides on its own: an answered one copies, an unanswered
    one stays NULL — no all-or-nothing bundle."""
    async with _client() as client:
        first_id = await _create_novel(client, "Das Atelier-Buch")
        await _write_answers(first_id, author_typology="pantser", canon_strictness=5)
        new_id = await _create_novel(client, "Die Prüferin")

    assert await _stored_answers(new_id) == ("pantser", None, None, 5)


async def test_the_copy_never_mutates_the_source_row() -> None:
    async with _client() as client:
        first_id = await _create_novel(client, "Das Atelier-Buch")
        await _write_answers(first_id, **ATELIER_ANSWERS)
        async with Session() as session:
            source = await session.get(Novel, UUID(first_id))
            assert source is not None
            source_updated_at = source.updated_at

        await _create_novel(client, "Die Prüferin")

    async with Session() as session:
        source = await session.get(Novel, UUID(first_id))
        assert source is not None
        assert (
            source.author_typology,
            source.dramatic_form,
            source.ai_role,
            source.canon_strictness,
        ) == ("plantser", "three-act", "lektor", 3)
        # The inheritance is a read of the source, not a write: its own
        # "last written" stands where it was.
        assert source.updated_at == source_updated_at


async def test_the_oldest_book_is_the_source() -> None:
    """The atelier's answers live on the FIRST book — the oldest created_at,
    the one setup made — not on the newest book's later edits."""
    now = datetime.now(UTC)
    async with Session() as session:
        session.add(
            Novel(
                user_id=LOCAL_USER_ID,
                title="Das Atelier-Buch",
                created_at=now - timedelta(days=2),
                updated_at=now - timedelta(days=2),
                author_typology="plotter",
                dramatic_form="five-act",
                ai_role="archivar",
                canon_strictness=1,
            )
        )
        session.add(
            Novel(
                user_id=LOCAL_USER_ID,
                title="Das zweite Buch",
                created_at=now - timedelta(days=1),
                updated_at=now - timedelta(days=1),
                author_typology="pantser",
                dramatic_form="three-act",
                ai_role="coautor",
                canon_strictness=5,
            )
        )
        await session.commit()

    async with _client() as client:
        new_id = await _create_novel(client, "Die Prüferin")

    assert await _stored_answers(new_id) == ("plotter", "five-act", "archivar", 1)


async def test_without_a_source_book_the_answers_stay_null() -> None:
    """No novel exists yet (the setup book was deleted, or never was): there
    is nothing to inherit, and the new book lies about nothing."""
    async with _client() as client:
        new_id = await _create_novel(client, "Die Prüferin")

    assert await _stored_answers(new_id) == (None, None, None, None)


async def test_an_archived_first_book_still_answers() -> None:
    """Archiving is the shelf's organization, not an erasure: the atelier's
    answers stand on the row, and the oldest book carries them still."""
    async with _client() as client:
        first_id = await _create_novel(client, "Das Atelier-Buch")
        await _write_answers(first_id, **ATELIER_ANSWERS)
        archived = await client.patch(
            f"/api/writing/novels/{first_id}",
            json={"archived_at": datetime.now(UTC).isoformat()},
        )
        assert archived.status_code == 200

        new_id = await _create_novel(client, "Die Prüferin")

    assert await _stored_answers(new_id) == ("plantser", "three-act", "lektor", 3)


async def test_another_users_book_is_not_the_source() -> None:
    """The source is the USER's first book: a foreign novel — older, answered —
    never feeds the local shelf's inheritance."""
    await seed_user(OTHER_USER)
    now = datetime.now(UTC)
    async with Session() as session:
        session.add(
            Novel(
                user_id=OTHER_USER,
                title="Fremd",
                created_at=now - timedelta(days=2),
                updated_at=now - timedelta(days=2),
                author_typology="plotter",
                dramatic_form="five-act",
                ai_role="archivar",
                canon_strictness=1,
            )
        )
        await session.commit()

    async with _client() as client:
        new_id = await _create_novel(client, "Die Prüferin")

    assert await _stored_answers(new_id) == (None, None, None, None)


async def test_a_new_book_inherits_the_ateliers_author_name() -> None:
    """The book-settings draft's atelier note (W4 Task 19, D22): the
    standard author name „wird automatisch in neue Manuskripte eingesetzt"
    — the create copies the user row's answer onto the new book."""
    async with _client() as client:
        written = await client.patch(
            "/api/settings", json={"locale": None, "author_name": "H. Calder"}
        )
        assert written.status_code == 200
        new_id = await _create_novel(client, "Die Prüferin")
        read = await client.get(f"/api/writing/novels/{new_id}")
        assert read.json()["author"] == "H. Calder"


async def test_no_author_name_stays_no_author() -> None:
    """The unset atelier name inherits the absence, never a guessed label
    (the email fallback is the chrome's rendering, not a book's author)."""
    async with _client() as client:
        new_id = await _create_novel(client, "Die Prüferin")
        read = await client.get(f"/api/writing/novels/{new_id}")
        assert read.json()["author"] is None
