"""The atelier's activity: daily net words, the streak and the window.

Every figure traces to a ``daily_words`` row the chapter write path fed:
the diff of the shelf's one whitespace rule, the OLD body read before the
update lands, same-day upserts accumulating, deletes counting negative.
The aggregate spans the user's novels and never another user's rows.

The disclosed decisions these tests pin: a day is active when its net is
nonzero (writing and revising both count); the streak ends today, or
yesterday when today has not been written in yet; the average is the mean
net words per day over ALL days of the window, zero-days included.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, update

from app.api.main import app
from app.capabilities.writing.models import DailyWords
from app.capabilities.writing.repository import DailyWordsRepository, NovelRepository
from app.capabilities.writing.schemas import ChapterUpdate
from app.capabilities.writing.service import WritingService
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")


def _today() -> date:
    return datetime.now(UTC).date()


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _create_novel(client: AsyncClient, title: str) -> str:
    response = await client.post("/api/writing/novels", json={"title": title})
    assert response.status_code == 201
    return response.json()["id"]


async def _add_chapter(client: AsyncClient, novel_id: str, body: str) -> str:
    created = await client.post(
        f"/api/writing/novels/{novel_id}/chapters", json={"title": "Kapitel"}
    )
    assert created.status_code == 201
    chapter_id = created.json()["id"]
    saved = await client.put(f"/api/writing/chapters/{chapter_id}", json={"body": body})
    assert saved.status_code == 200
    return chapter_id


async def _activity(client: AsyncClient, days: int | None = None) -> dict[str, Any]:
    params = {} if days is None else {"days": days}
    response = await client.get("/api/writing/activity", params=params)
    assert response.status_code == 200
    return response.json()


async def _seed_words(novel_id: str, day: date, words: int, user_id: UUID = LOCAL_USER_ID) -> None:
    """One day's net words, seeded through the repository the write path uses."""
    async with Session() as session:
        await DailyWordsRepository(session, user_id).add_words(UUID(novel_id), day, words)
        await session.commit()


async def _move_rows_to(novel_id: str, day: date) -> None:
    """Move the novel's activity rows to another day — the test's clock seam:
    the write path always stamps today, so a past day is seeded, not waited for."""
    async with Session() as session:
        await session.execute(
            update(DailyWords).where(DailyWords.novel_id == UUID(novel_id)).values(date=day)
        )
        await session.commit()


def _point_dates(body: dict[str, Any]) -> list[date]:
    return [date.fromisoformat(point["date"]) for point in body["points"]]


def _assert_window(body: dict[str, Any], days: int) -> None:
    """The points are exactly the requested window, oldest first, ending today."""
    today = _today()
    assert _point_dates(body) == [today - timedelta(days=days - 1 - i) for i in range(days)]


async def test_a_fresh_atelier_reports_an_honest_zero_window() -> None:
    async with _client() as client:
        body = await _activity(client)
        _assert_window(body, 30)
        assert all(point["words"] == 0 for point in body["points"])
        assert body["streak_days"] == 0
        assert body["weekly_average"] == 0.0
        assert body["today_words"] == 0


async def test_create_update_delete_nets_zero_same_day() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        created = await client.post(
            f"/api/writing/novels/{novel_id}/chapters", json={"title": "Kapitel"}
        )
        assert created.status_code == 201
        chapter_id = created.json()["id"]
        # A chapter is born empty: the create itself writes no words.
        assert (await _activity(client))["today_words"] == 0

        saved = await client.put(
            f"/api/writing/chapters/{chapter_id}", json={"body": "eins zwei drei"}
        )
        assert saved.status_code == 200
        body = await _activity(client)
        assert body["today_words"] == 3
        assert body["streak_days"] == 1

        # The diff, not the new total: five words after three is +2, not +5.
        await client.put(
            f"/api/writing/chapters/{chapter_id}", json={"body": "eins zwei drei vier fünf"}
        )
        assert (await _activity(client))["today_words"] == 5
        await client.put(f"/api/writing/chapters/{chapter_id}", json={"body": "eins"})
        assert (await _activity(client))["today_words"] == 1

        deleted = await client.delete(f"/api/writing/chapters/{chapter_id}")
        assert deleted.status_code == 204
        body = await _activity(client)
        assert body["today_words"] == 0
        assert body["streak_days"] == 0
        assert all(point["words"] == 0 for point in body["points"])


async def test_the_same_text_added_then_removed_same_day_nets_zero() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        chapter_id = await _add_chapter(client, novel_id, "alpha beta gamma")
        assert (await _activity(client))["today_words"] == 3

        await client.put(f"/api/writing/chapters/{chapter_id}", json={"body": ""})
        body = await _activity(client)
        assert body["today_words"] == 0
        assert body["streak_days"] == 0

        # The day's row accumulated back to zero, and accumulates on again.
        await client.put(f"/api/writing/chapters/{chapter_id}", json={"body": "alpha beta gamma"})
        assert (await _activity(client))["today_words"] == 3


async def test_same_day_writes_accumulate_across_chapters_and_novels() -> None:
    async with _client() as client:
        first_id = await _create_novel(client, "Erstes")
        second_id = await _create_novel(client, "Zweites")
        await _add_chapter(client, first_id, "eins zwei")
        await _add_chapter(client, second_id, "drei vier fünf")

        body = await _activity(client)
        assert body["today_words"] == 5
        assert body["streak_days"] == 1
        assert [point["words"] for point in body["points"] if point["words"]] == [5]

        # One row per novel and day — the upsert accumulates, never doubles.
        async with Session() as session:
            rows = await session.scalar(select(func.count()).select_from(DailyWords))
        assert rows == 2


async def test_a_title_only_edit_records_no_activity() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        chapter_id = await _add_chapter(client, novel_id, "")
        await client.put(f"/api/writing/chapters/{chapter_id}", json={"title": "Neuer Name"})
        # A carried body that counts the same is no write either.
        await client.put(f"/api/writing/chapters/{chapter_id}", json={"body": ""})

        body = await _activity(client)
        assert body["today_words"] == 0
        assert body["streak_days"] == 0


async def test_the_word_rule_is_the_shelves_own() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Abstand")
        # The one whitespace class: NBSP, figure space and narrow no-break
        # space split; the ends trim; the wide space is whitespace too.
        near = chr(0x00A0) + "zwei" + chr(0x2007) + "drei" + chr(0x202F) + "vier"
        await _add_chapter(client, novel_id, "  eins" + near + "  ")
        await _add_chapter(client, novel_id, chr(0x3000) + " \t")

        body = await _activity(client)
        assert body["today_words"] == 4
        # The shelf's derived count and the activity agree — one rule.
        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        assert fetched.json()["word_count"] == 4


async def test_deleting_a_chapter_counts_negative_on_a_later_day() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        chapter_id = await _add_chapter(client, novel_id, "eins zwei drei vier fünf")
        # The five words were written yesterday; today only removes them.
        await _move_rows_to(novel_id, _today() - timedelta(days=1))

        deleted = await client.delete(f"/api/writing/chapters/{chapter_id}")
        assert deleted.status_code == 204
        body = await _activity(client)
        assert body["today_words"] == -5
        assert body["points"][-2]["words"] == 5
        # Nonzero days are active days — revising counts, the net is honest:
        # yesterday wrote five, today removed five, two consecutive days.
        assert body["streak_days"] == 2
        # The window's net is zero: five written, five removed.
        assert body["weekly_average"] == 0.0


async def test_points_cover_the_window_including_zero_days() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        await _seed_words(novel_id, _today() - timedelta(days=1), 100)

        body = await _activity(client, days=7)
        _assert_window(body, 7)
        assert body["points"][-2]["words"] == 100
        assert [point["words"] for point in body["points"]] == [0, 0, 0, 0, 0, 100, 0]
        assert body["today_words"] == 0


@pytest.mark.parametrize("days", [1, 365])
async def test_the_window_bounds_are_inclusive(days: int) -> None:
    async with _client() as client:
        body = await _activity(client, days=days)
        _assert_window(body, days)


@pytest.mark.parametrize("days", [0, -1, 366])
async def test_a_window_outside_the_bounds_is_refused(days: int) -> None:
    async with _client() as client:
        response = await client.get("/api/writing/activity", params={"days": days})
        assert response.status_code == 422


async def test_the_streak_counts_consecutive_days_ending_today() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        for offset in range(3):
            await _seed_words(novel_id, _today() - timedelta(days=offset), 100)
        assert (await _activity(client))["streak_days"] == 3


async def test_yesterday_only_keeps_the_streak_alive() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        await _seed_words(novel_id, _today() - timedelta(days=1), 100)
        await _seed_words(novel_id, _today() - timedelta(days=2), 100)
        body = await _activity(client)
        assert body["streak_days"] == 2
        assert body["today_words"] == 0


async def test_the_day_before_yesterday_alone_breaks_the_streak() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        await _seed_words(novel_id, _today() - timedelta(days=2), 100)
        assert (await _activity(client))["streak_days"] == 0


async def test_a_gap_breaks_the_streak() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        await _seed_words(novel_id, _today(), 100)
        await _seed_words(novel_id, _today() - timedelta(days=1), 100)
        await _seed_words(novel_id, _today() - timedelta(days=3), 100)
        assert (await _activity(client))["streak_days"] == 2


async def test_the_streak_reaches_past_the_window() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        for offset in range(40):
            await _seed_words(novel_id, _today() - timedelta(days=offset), 10)
        body = await _activity(client, days=7)
        _assert_window(body, 7)
        assert body["streak_days"] == 40


async def test_a_day_nets_across_novels_before_it_counts() -> None:
    async with _client() as client:
        first_id = await _create_novel(client, "Erstes")
        second_id = await _create_novel(client, "Zweites")
        # Yesterday the atelier wrote and removed the same amount: net zero,
        # no active day. Today it wrote: the streak starts here, not yesterday.
        await _seed_words(first_id, _today() - timedelta(days=1), 50)
        await _seed_words(second_id, _today() - timedelta(days=1), -50)
        await _seed_words(first_id, _today(), 10)
        body = await _activity(client)
        assert body["streak_days"] == 1
        assert body["today_words"] == 10


async def test_the_aggregate_never_counts_another_users_rows() -> None:
    await seed_user(OTHER_USER)
    async with Session() as session:
        foreign = await NovelRepository(session, OTHER_USER).create("Fremdes Buch")
        await session.commit()
        foreign_id = str(foreign.id)
    for offset in range(10):
        await _seed_words(foreign_id, _today() - timedelta(days=offset), 1000, OTHER_USER)

    async with _client() as client:
        novel_id = await _create_novel(client, "Mein")
        await _add_chapter(client, novel_id, "eins zwei")
        body = await _activity(client)
        assert body["today_words"] == 2
        assert body["streak_days"] == 1
        assert body["weekly_average"] == round(2 / 30, 1)
        assert sum(point["words"] for point in body["points"]) == 2


async def test_weekly_average_is_the_mean_over_all_window_days() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        await _seed_words(novel_id, _today(), 300)
        # Zero-days count in the basis: 300 words over 30 days is 10 a day,
        # over 7 days 42.9 — not 300, the active-day answer.
        assert (await _activity(client))["weekly_average"] == 10.0
        assert (await _activity(client, days=7))["weekly_average"] == round(300 / 7, 1)

        await _seed_words(novel_id, _today(), -200)
        # The net is the numerator: 100 over 30 days, one decimal.
        assert (await _activity(client))["weekly_average"] == round(100 / 30, 1)


async def test_deleting_a_novel_takes_its_activity_with_it() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        await _add_chapter(client, novel_id, "eins zwei drei vier")
        assert (await _activity(client))["today_words"] == 4

        deleted = await client.delete(f"/api/writing/novels/{novel_id}")
        assert deleted.status_code == 204
        body = await _activity(client)
        assert body["today_words"] == 0
        assert body["streak_days"] == 0


async def test_a_new_day_starts_a_fresh_row() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        chapter_id = await _add_chapter(client, novel_id, "eins zwei drei")
        await _move_rows_to(novel_id, _today() - timedelta(days=1))

        # Two more words today: the diff lands on today's own row.
        await client.put(
            f"/api/writing/chapters/{chapter_id}", json={"body": "eins zwei drei vier fünf"}
        )
        body = await _activity(client)
        assert body["points"][-2]["words"] == 3
        assert body["today_words"] == 2
        assert body["streak_days"] == 2


async def test_a_double_fired_save_counts_the_diff_once() -> None:
    """The race the novel lock closes, at service level: two saves of the
    same body, the second holding its pre-lock read while the first
    commits. The day's row must gain the words ONCE — the diff counts
    from the body re-read under the lock, not the stale snapshot.

    The pre-read is held in a local on purpose: the session's identity
    map is weak-valued, so a discarded read would be collected and the
    save's own get would reload fresh — the race would hide. Production
    holds the read the same way, in update_chapter's own local."""
    async with Session() as first, Session() as second:
        writer = WritingService(first, LOCAL_USER_ID)
        novel = await writer.create_novel("Der Nebel")
        chapter = await writer.create_chapter(novel.id, "Kapitel")
        await writer.update_chapter(chapter.id, ChapterUpdate(body="eins zwei drei"))

        # The second-fired save reads the chapter BEFORE the first-fired
        # save lands: its session's identity map holds the three-word body.
        reader = WritingService(second, LOCAL_USER_ID)
        stale_read = await reader.get_chapter(chapter.id)
        assert stale_read.body == "eins zwei drei"

        # The first-fired save wins the lock and commits five words.
        await writer.update_chapter(chapter.id, ChapterUpdate(body="eins zwei drei vier fünf"))

        # The second-fired save lands the same body: its pre-lock read is
        # stale, but under the lock the committed body is already five
        # words — the diff is zero, the day keeps five, not seven.
        await reader.update_chapter(chapter.id, ChapterUpdate(body="eins zwei drei vier fünf"))

    async with _client() as client:
        body = await _activity(client)
        assert body["today_words"] == 5


async def test_a_delete_counts_the_words_the_book_actually_holds() -> None:
    """The delete's pre-lock read can be stale the same way: a concurrent
    save grew the chapter after the read. The day's row must lose the
    words the book holds at the delete, not the ones the session
    remembers. The pre-read is held for the identity map's weak values,
    as in the double-fired save's pin."""
    async with Session() as first, Session() as second:
        writer = WritingService(first, LOCAL_USER_ID)
        novel = await writer.create_novel("Der Nebel")
        chapter = await writer.create_chapter(novel.id, "Kapitel")
        await writer.update_chapter(chapter.id, ChapterUpdate(body="eins zwei drei"))

        # The delete's pre-lock read: three words in this session's map.
        reader = WritingService(second, LOCAL_USER_ID)
        stale_read = await reader.get_chapter(chapter.id)
        assert stale_read.body == "eins zwei drei"

        # A concurrent save grows the book to five words and commits.
        await writer.update_chapter(chapter.id, ChapterUpdate(body="eins zwei drei vier fünf"))

        # The delete lands: five words go, the day nets zero — not the two
        # a stale three-word subtraction would leave behind.
        await reader.delete_chapter(chapter.id)

    async with _client() as client:
        body = await _activity(client)
        assert body["today_words"] == 0
