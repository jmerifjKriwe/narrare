"""Duplicating a novel: one transaction copies the book and every chapter.

The copy keeps the book's own facts — genre, front matter, the wizard's
settings, status, the series link — and its chapters' titles and positions,
with each chapter's scenes (prose, overline, in-story label) riding along.
The shelf's tracking starts fresh: no volume, no archive
stamp, no export trace. The refusals are the shelf's own: a foreign or
unknown book is a 404 that writes nothing, and a copy that dies mid-write
leaves no half book behind.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, event
from sqlalchemy.orm import Session as OrmSession

from app.api.main import app
from app.capabilities.writing.repository import ChapterRepository, SeriesRepository
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Chapter, Novel, User
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

if TYPE_CHECKING:
    from collections.abc import Sequence

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _create_novel(client: AsyncClient, title: str = "Der Nebel") -> str:
    response = await client.post("/api/writing/novels", json={"title": title})
    assert response.status_code == 201
    return response.json()["id"]


async def _add_chapter(client: AsyncClient, novel_id: str, title: str, body: str) -> str:
    created = await client.post(f"/api/writing/novels/{novel_id}/chapters", json={"title": title})
    assert created.status_code == 201
    chapter_id = created.json()["id"]
    # The prose lives on a scene now (W4 §5): the chapter is the shell.
    written = await client.post(f"/api/writing/chapters/{chapter_id}/scenes", json={"body": body})
    assert written.status_code == 201
    return chapter_id


async def _create_series(title: str) -> str:
    async with Session() as session:
        series = await SeriesRepository(session, LOCAL_USER_ID).create(title)
        await session.commit()
        return str(series.id)


async def test_the_copy_carries_the_books_own_facts() -> None:
    series_id = await _create_series("Die Nebel-Chroniken")
    async with _client() as client:
        novel_id = await _create_novel(client)
        # The wizard's answers, written the way the wizard writes them:
        # on the row itself (the setup capability owns that door).
        async with Session() as session:
            novel = await session.get(Novel, UUID(novel_id))
            assert novel is not None
            novel.target_words = 65000
            novel.author_typology = "plotter"
            novel.dramatic_form = "three-act"
            novel.ai_role = "coautor"
            novel.canon_strictness = 4
            await session.commit()
        patched = await client.patch(
            f"/api/writing/novels/{novel_id}",
            json={
                "genre": "Mystery",
                "blurb": "A fog rolls in.",
                "author": "J. Autorin",
                "language": "de",
                "status": "revision",
                "series_id": series_id,
                "series_volume": 2,
            },
        )
        assert patched.status_code == 200

        duplicated = await client.post(f"/api/writing/novels/{novel_id}/duplicate")
        assert duplicated.status_code == 201
        copy = duplicated.json()
        assert copy["id"] != novel_id
        assert copy["title"] == '„Der Nebel (Kopie)"'
        assert copy["genre"] == "Mystery"
        assert copy["blurb"] == "A fog rolls in."
        assert copy["author"] == "J. Autorin"
        assert copy["language"] == "de"
        assert copy["status"] == "revision"
        # The series link rides; the volume belongs to the original's place.
        assert copy["series_title"] == "Die Nebel-Chroniken"
        assert copy["series_volume"] is None
        # The copy starts on the shelf, never exported.
        assert copy["archived_at"] is None
        assert copy["last_exported_at"] is None

    # The wizard's settings are the row's own: read them where they live.
    async with Session() as session:
        stored = await session.get(Novel, UUID(copy["id"]))
        assert stored is not None
        assert stored.user_id == LOCAL_USER_ID
        assert stored.target_words == 65000
        assert stored.author_typology == "plotter"
        assert stored.dramatic_form == "three-act"
        assert stored.ai_role == "coautor"
        assert stored.canon_strictness == 4
        assert stored.series_id == UUID(series_id)
        assert stored.series_volume is None
        assert stored.archived_at is None
        assert stored.last_exported_at is None


async def test_the_chapters_keep_titles_positions_and_their_scenes() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client)
        first = await _add_chapter(
            client, novel_id, "Ankunft", "Der Nebel legt sich über die Bucht."
        )
        await _add_chapter(client, novel_id, "Die Stadt", "Gassen wie graue Bänder.")
        await _add_chapter(client, novel_id, "Der Turm", "Ein Licht dreht sich im Kreis.")
        # The overline and in-story label ride the copy too: label the first
        # chapter's scene so the assertion has something to carry.
        first_scene = (await client.get(f"/api/writing/chapters/{first}/scenes")).json()[0]
        labeled = await client.put(
            f"/api/writing/scenes/{first_scene['id']}",
            json={"setting": "Hafen bei Nacht", "story_time": "Dritte Stunde"},
        )
        assert labeled.status_code == 200
        # A rearranged rail: the copy keeps this order, not creation order.
        listed = (await client.get(f"/api/writing/novels/{novel_id}/chapters")).json()
        reordered = [listed[2]["id"], listed[0]["id"], listed[1]["id"]]
        moved = await client.put(
            f"/api/writing/novels/{novel_id}/chapter-order", json={"chapter_ids": reordered}
        )
        assert moved.status_code == 204
        original_novel = (await client.get(f"/api/writing/novels/{novel_id}")).json()

        duplicated = await client.post(f"/api/writing/novels/{novel_id}/duplicate")
        assert duplicated.status_code == 201
        copy = duplicated.json()

        original = (await client.get(f"/api/writing/novels/{novel_id}/chapters")).json()
        copied = (await client.get(f"/api/writing/novels/{copy['id']}/chapters")).json()
        assert [(c["title"], c["position"]) for c in copied] == [
            (c["title"], c["position"]) for c in original
        ]
        assert [c["position"] for c in copied] == [0, 1, 2]
        # New rows, not shared ones.
        assert {c["id"] for c in copied}.isdisjoint({c["id"] for c in original})
        # The prose rides the scenes: each copy chapter carries its original's
        # scenes — body, overline, in-story label and position — as new rows.
        for source, target in zip(original, copied, strict=True):
            source_scenes = (
                await client.get(f"/api/writing/chapters/{source['id']}/scenes")
            ).json()
            target_scenes = (
                await client.get(f"/api/writing/chapters/{target['id']}/scenes")
            ).json()
            assert [
                (s["title"], s["body"], s["setting"], s["story_time"], s["position"])
                for s in target_scenes
            ] == [
                (s["title"], s["body"], s["setting"], s["story_time"], s["position"])
                for s in source_scenes
            ]
            assert {s["id"] for s in target_scenes}.isdisjoint({s["id"] for s in source_scenes})
        assert copy["chapter_count"] == 3
        assert copy["word_count"] == original_novel["word_count"]


async def test_the_copy_is_immediately_on_the_shelf() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client)
        await _add_chapter(client, novel_id, "Ankunft", "Der Nebel legt sich über die Bucht.")

        duplicated = await client.post(f"/api/writing/novels/{novel_id}/duplicate")
        assert duplicated.status_code == 201
        copy = duplicated.json()

        # Newest first: the copy leads the grid, with its real counts.
        listed = (await client.get("/api/writing/novels")).json()
        assert [novel["id"] for novel in listed] == [copy["id"], novel_id]
        assert listed[0]["chapter_count"] == 1
        assert listed[0]["word_count"] == 7

        fetched = await client.get(f"/api/writing/novels/{copy['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["chapter_count"] == 1
        assert fetched.json()["word_count"] == 7


async def test_an_empty_book_duplicates_too() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client)
        duplicated = await client.post(f"/api/writing/novels/{novel_id}/duplicate")
        assert duplicated.status_code == 201
        copy = duplicated.json()
        assert copy["chapter_count"] == 0
        assert copy["word_count"] == 0
        assert (await client.get(f"/api/writing/novels/{copy['id']}/chapters")).json() == []


async def test_the_archive_stamp_is_not_copied() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client)
        await _add_chapter(client, novel_id, "Ankunft", "Der Nebel.")
        stamp = datetime.now(UTC)
        archived = await client.patch(
            f"/api/writing/novels/{novel_id}", json={"archived_at": stamp.isoformat()}
        )
        assert archived.status_code == 200
        assert (await client.get("/api/writing/novels")).json() == []

        # The editor still reaches the archived book — and can copy it.
        duplicated = await client.post(f"/api/writing/novels/{novel_id}/duplicate")
        assert duplicated.status_code == 201
        copy = duplicated.json()
        assert copy["archived_at"] is None
        assert copy["chapter_count"] == 1

        # The copy is on the shelf; the original stays archived.
        listed = (await client.get("/api/writing/novels")).json()
        assert [novel["id"] for novel in listed] == [copy["id"]]
        original = (await client.get(f"/api/writing/novels/{novel_id}")).json()
        assert datetime.fromisoformat(original["archived_at"]) == stamp


async def test_a_foreign_novel_is_404_and_writes_nothing() -> None:
    await seed_user(OTHER_USER)
    async with Session() as session:
        foreign = Novel(user_id=OTHER_USER, title="Fremd")
        session.add(foreign)
        await session.flush()
        session.add(
            Chapter(
                user_id=OTHER_USER, novel_id=foreign.id, title="Kapitel", position=0, body="Text"
            )
        )
        await session.commit()
        foreign_id = foreign.id

    async with _client() as client:
        refused = await client.post(f"/api/writing/novels/{foreign_id}/duplicate")
        assert refused.status_code == 404
        assert refused.json()["detail"] == "novel not found"
        # The refusal wrote nothing: no copy on the local shelf.
        assert (await client.get("/api/writing/novels")).json() == []

    # The foreign book keeps its rows.
    async with Session() as session:
        kept = await session.get(Novel, foreign_id)
        assert kept is not None
        assert kept.title == "Fremd"


async def test_a_never_known_id_is_404() -> None:
    async with _client() as client:
        refused = await client.post(f"/api/writing/novels/{uuid4()}/duplicate")
        assert refused.status_code == 404
        assert refused.json()["detail"] == "novel not found"


async def test_a_long_title_keeps_as_much_of_itself_as_fits() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "x" * 200)
        duplicated = await client.post(f"/api/writing/novels/{novel_id}/duplicate")
        assert duplicated.status_code == 201
        copy_title = duplicated.json()["title"]
        assert len(copy_title) == 200
        assert copy_title == f'„{"x" * 190} (Kopie)"'


async def test_without_the_setup_user_the_copy_is_409() -> None:
    async with Session() as session:
        await session.execute(delete(User).where(User.id == LOCAL_USER_ID))
        await session.commit()

    async with _client() as client:
        refused = await client.post(f"/api/writing/novels/{uuid4()}/duplicate")
        assert refused.status_code == 409
        assert refused.json() == {"detail": "setup required"}


async def test_a_failing_chapter_copy_leaves_no_half_book(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Novel and chapters are one transaction: when the chapter copy dies,
    the flushed novel row dies with it — no half book on the shelf."""
    async with _client() as client:
        novel_id = await _create_novel(client)
        await _add_chapter(client, novel_id, "Ankunft", "Der Nebel.")

    async def broken_copy(
        self: ChapterRepository, novel_id: UUID, chapters: Sequence[Chapter]
    ) -> None:
        raise RuntimeError("the copy died mid-write")

    monkeypatch.setattr(ChapterRepository, "copy_into", broken_copy)
    async with _client() as client:
        with pytest.raises(RuntimeError, match="the copy died mid-write"):
            await client.post(f"/api/writing/novels/{novel_id}/duplicate")
        # The original is untouched and alone: the refused copy committed
        # neither its novel row nor any chapter.
        listed = (await client.get("/api/writing/novels")).json()
        assert [novel["id"] for novel in listed] == [novel_id]
        assert listed[0]["chapter_count"] == 1


async def test_the_copy_lands_in_one_commit() -> None:
    """The whole copy — novel row and every chapter — is one commit."""
    async with _client() as client:
        novel_id = await _create_novel(client)
        await _add_chapter(client, novel_id, "Ankunft", "Der Nebel.")
        await _add_chapter(client, novel_id, "Die Stadt", "Gassen.")

        commits = 0

        def count_commit(session: OrmSession) -> None:
            nonlocal commits
            commits += 1

        # The sync session class is the event target: the request's
        # AsyncSession wraps one, and its commits fire here.
        event.listen(OrmSession, "after_commit", count_commit)
        try:
            duplicated = await client.post(f"/api/writing/novels/{novel_id}/duplicate")
        finally:
            event.remove(OrmSession, "after_commit", count_commit)
        assert duplicated.status_code == 201
        assert commits == 1
