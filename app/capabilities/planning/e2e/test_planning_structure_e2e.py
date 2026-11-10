"""The structure canvas: the story's shape as a proportion bar.

The timeline landing is the canvas's one door (beside the storyboard): the
novel's stages stand as one band each, each band as wide as its share of
the story, the chapters inside their band in position order, with the
deviation count summarized above. A click on a chapter walks to the
workspace. At 1280 px the page fits its viewport: no document-level
horizontal scroll.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import httpx
import pytest
from playwright.sync_api import Page, expect

from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.stack import API_URL, WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

# The API the stack runs, for seeding a novel with chapters the way a user
# would build them — through the real service, no shortcuts.
API = API_URL


def _seed_novel(novel_title: str, chapters: list[str]) -> tuple[str, list[str]]:
    """A novel with chapters in seed order, through the API.

    Returns the novel's id (the canvas's `?novel=` parameter) and the
    chapter ids in seed order. Positions follow creation order, so the
    first chapter suggests the first stage and the last the final one.
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


def _seed_words(novel_id: str, chapter_id: str, body: str) -> None:
    """Prose on the chapter, so the word count reads above zero."""
    with httpx.Client(base_url=API, timeout=30) as api:
        updated = api.put(f"/api/writing/chapters/{chapter_id}", json={"body": body})
        updated.raise_for_status()


def _seed_scenes(novel_id: str, chapter_id: str, scenes: list[dict[str, str]]) -> None:
    """Scene plans on the chapter, through the real service."""
    with httpx.Client(base_url=API, timeout=30) as api:
        saved = api.put(
            f"/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes",
            json={"scenes": scenes},
        )
        saved.raise_for_status()


def _move_stage(novel_id: str, chapter_id: str, stage_key: str) -> None:
    """A hand-set stage, off the suggestion — the sync rule's deviation."""
    with httpx.Client(base_url=API, timeout=30) as api:
        moved = api.put(
            f"/api/planning/novels/{novel_id}/chapters/{chapter_id}/stage",
            json={"stage_key": stage_key},
        )
        moved.raise_for_status()


def _seed_board(novel_title: str = "Die vermessene Bucht") -> tuple[str, list[str]]:
    """One novel whose last chapter carries words but stands off its
    suggested stage — the deviation the canvas marks."""
    novel_id, (ankunft, abreise, heimkehr) = _seed_novel(
        novel_title, ["Ankunft", "Abreise", "Heimkehr"]
    )
    _seed_scenes(novel_id, ankunft, [{"id": str(uuid4()), "title": "Sturm", "status": "planned"}])
    _seed_words(novel_id, heimkehr, "Erste Worte im Manuskript.")
    _move_stage(novel_id, heimkehr, "setup")
    return novel_id, [ankunft, abreise, heimkehr]


def test_the_canvas_proportions_stages_and_marks_the_deviation(page: Page, stack: Stack) -> None:
    novel_id, chapters = _seed_board("Die vermessene Bucht")
    heimkehr_id = chapters[2]
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(f"{WEB_URL}/planning")
    page.get_by_role("link", name="Die vermessene Bucht").click()
    page.get_by_role("link", name="Struktur öffnen").click()

    expect(page.get_by_role("heading", name="Struktur")).to_be_visible()
    expect(page.get_by_role("region", name="Exposition")).to_be_visible()
    expect(page.get_by_role("region", name="Konfrontation")).to_be_visible()
    expect(page.get_by_role("region", name="Auflösung")).to_be_visible()

    # The summary counts the story: three chapters, four words, one drift.
    expect(page.get_by_text("3 Kapitel · 4 Wörter · 1 Abweichung")).to_be_visible()

    # The drifted chapter stands in its hand-set band and wears its name —
    # a badge with the word, never colour alone.
    exposition = page.get_by_role("region", name="Exposition")
    expect(exposition.get_by_text("Abgewichen")).to_be_visible()

    # The mark walks to the chapter in the workspace.
    exposition.get_by_role("link", name="Heimkehr").click()
    expect(page).to_have_url(f"{WEB_URL}/novels/{novel_id}?chapter={heimkehr_id}")

    fits = page.evaluate(
        """() => ({
            documentWidth: document.documentElement.scrollWidth,
            viewportWidth: window.innerWidth,
            mainWidth: document.getElementById("main").scrollWidth,
            mainClient: document.getElementById("main").clientWidth,
        })"""
    )
    assert fits["documentWidth"] <= fits["viewportWidth"]
    assert fits["mainWidth"] <= fits["mainClient"] + 1

    assert_accessible(page)
