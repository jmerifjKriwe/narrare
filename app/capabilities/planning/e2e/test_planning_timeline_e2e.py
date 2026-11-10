"""The Planen landing canvas: the novel's timeline as a full page.

The rail entry is generated (planning exports nav, no hand-written nav) and
lands on the picker at `/planning`; the novel's events render in the
writer's own order, the by-chapter view groups them under their chapters,
and an add through the dialog persists across a reload. At 1280 px the page
fits its viewport: no document-level scroll in either axis.
"""

from typing import TYPE_CHECKING

import httpx
import pytest
from playwright.sync_api import Page, expect

from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.stack import API_URL, WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

# The API the stack runs, for seeding a novel with chapters and events the
# way a user would build them — through the real service, no shortcuts.
API = API_URL


def _seed_novel(novel_title: str, chapters: list[str]) -> tuple[str, list[str]]:
    """A novel with chapters, through the API.

    Returns the novel's id (the timeline's `?novel=` parameter) and the
    chapter ids in seed order, for the event payloads to link against.
    """
    with httpx.Client(base_url=API, timeout=30) as api:
        novel = api.post("/api/writing/novels", json={"title": novel_title})
        novel.raise_for_status()
        novel_id = novel.json()["id"]
        chapter_ids: list[str] = []
        for title in chapters:
            chapter = api.post(f"/api/writing/novels/{novel_id}/chapters", json={"title": title})
            chapter.raise_for_status()
            chapter_ids.append(chapter.json()["id"])
    return novel_id, chapter_ids


def _seed_event(novel_id: str, payload: dict[str, object]) -> None:
    """One timeline event on the novel, through the real service."""
    with httpx.Client(base_url=API, timeout=30) as api:
        created = api.post(f"/api/planning/novels/{novel_id}/timeline-events", json=payload)
        created.raise_for_status()


def test_the_timeline_landing_shows_both_views_in_german(page: Page, stack: Stack) -> None:
    novel_id, (ankunft, abreise) = _seed_novel("Die geplante Bucht", ["Ankunft", "Abreise"])
    _seed_event(
        novel_id,
        {
            "title": "Anfang",
            "position": 1,
            "chapter_id": ankunft,
            "date_label": "Im Frühling",
        },
    )
    _seed_event(novel_id, {"title": "Mitte", "position": 2, "chapter_id": abreise})
    _seed_event(novel_id, {"title": "Ausklang", "position": 3})
    page.goto(f"{WEB_URL}/planning")
    page.get_by_role("link", name="Die geplante Bucht").click()

    expect(page.get_by_role("heading", name="Planung")).to_be_visible()
    expect(page.get_by_role("link", name="Anderen Roman wählen")).to_be_visible()

    # The chronological view is the default: the server's order, not the
    # alphabet's — Anfang (1), Mitte (2), Ausklang (3).
    rows = page.locator("main li")
    expect(rows).to_have_count(3)
    titles = [title.strip() for title in rows.all_text_contents()]
    assert (
        titles.index(next(t for t in titles if "Anfang" in t))
        < titles.index(next(t for t in titles if "Mitte" in t))
        < titles.index(next(t for t in titles if "Ausklang" in t))
    )
    # The dated row carries its garnish; undated rows show no date.
    expect(page.get_by_text("Im Frühling")).to_be_visible()

    # The by-chapter view groups the same events under their chapters,
    # chapterless rows last.
    page.get_by_role("button", name="Nach Kapiteln").click()
    ankunft_region = page.get_by_role("region", name="Ankunft")
    expect(ankunft_region.get_by_text("Anfang")).to_be_visible()
    abreise_region = page.get_by_role("region", name="Abreise")
    expect(abreise_region.get_by_text("Mitte")).to_be_visible()
    loose_region = page.get_by_role("region", name="Kein Kapitel")
    expect(loose_region.get_by_text("Ausklang")).to_be_visible()

    assert_accessible(page)


def test_an_added_event_persists_across_a_reload(page: Page, stack: Stack) -> None:
    _, _ = _seed_novel("Die leere Bucht", ["Ankunft"])
    page.goto(f"{WEB_URL}/planning")
    page.get_by_role("link", name="Die leere Bucht").click()

    # The honest empty names the next step, and the add stands beside it.
    expect(page.get_by_text("Noch keine Ereignisse. Lege unten das erste an.")).to_be_visible()
    page.get_by_role("button", name="Ereignis hinzufügen").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Titel").fill("Sturm")
    dialog.get_by_label("Datum (optional)").fill("Im Frühling")
    dialog.get_by_label("Kapitel (optional)").select_option(label="Ankunft")
    dialog.get_by_role("button", name="Ereignis hinzufügen").click()

    expect(page.get_by_role("group", name="Sturm")).to_be_visible()
    expect(page.get_by_text("Im Frühling")).to_be_visible()

    # The server kept the add: a reload shows the same row.
    page.reload()
    expect(page.get_by_role("group", name="Sturm")).to_be_visible()
    page.get_by_role("button", name="Nach Kapiteln").click()
    expect(page.get_by_role("region", name="Ankunft").get_by_text("Sturm")).to_be_visible()

    assert_accessible(page)


def test_the_timeline_fits_1280(page: Page, stack: Stack) -> None:
    """The landing canvas fits a 1280 px desk viewport: no page-level scroll."""
    novel_id, _ = _seed_novel("Die kurze Bucht", ["Ankunft"])
    _seed_event(novel_id, {"title": "Anfang", "position": 1, "date_label": "Im Frühling"})
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(f"{WEB_URL}/planning?novel={novel_id}")
    expect(page.get_by_role("heading", name="Planung")).to_be_visible()
    expect(page.get_by_role("group", name="Anfang")).to_be_visible()

    fits = page.evaluate(
        """() => ({
            documentWidth: document.documentElement.scrollWidth,
            documentHeight: document.documentElement.scrollHeight,
            viewportWidth: window.innerWidth,
            viewportHeight: window.innerHeight,
            mainWidth: document.getElementById("main").scrollWidth,
            mainClient: document.getElementById("main").clientWidth,
        })"""
    )
    assert fits["documentWidth"] <= fits["viewportWidth"]
    assert fits["mainWidth"] <= fits["mainClient"] + 1
    assert fits["documentHeight"] <= fits["viewportHeight"] + 1

    assert_accessible(page)
