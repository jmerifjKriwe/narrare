"""The storyboard canvas: chapters as cards in stage columns.

The timeline landing is the canvas's one door (the atlas names no other):
the novel's chapters stand in the columns of its structure with their word
counts and sync badges, a move menu per card rewrites the stage, and the
structure switcher previews the remap before it writes. At 1280 px the page
fits its viewport: no document-level horizontal scroll.
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

# The API the stack runs, for seeding a novel with chapters and scenes the
# way a user would build them — through the real service, no shortcuts.
API = API_URL


def _seed_novel(novel_title: str, chapters: list[str]) -> tuple[str, list[str]]:
    """A novel with chapters in seed order, through the API.

    Returns the novel's id (the canvas's `?novel=` parameter) and the
    chapter ids in seed order, for the scene payloads to link against.
    Positions follow creation order, so the first chapter suggests the
    first stage and the last the final one.
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


def _seed_scenes(novel_id: str, chapter_id: str, scenes: list[dict[str, str]]) -> None:
    """Scene plans on the chapter, through the real service."""
    with httpx.Client(base_url=API, timeout=30) as api:
        saved = api.put(
            f"/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes",
            json={"scenes": scenes},
        )
        saved.raise_for_status()


def _seed_words(novel_id: str, chapter_id: str, body: str) -> None:
    """Prose on the chapter, so the word count reads above zero."""
    with httpx.Client(base_url=API, timeout=30) as api:
        updated = api.put(f"/api/writing/chapters/{chapter_id}", json={"body": body})
        updated.raise_for_status()


def _scene(title: str, status: str = "planned") -> dict[str, str]:
    return {"id": str(uuid4()), "title": title, "status": status}


def _seed_board(novel_title: str = "Die aufgestellte Bucht") -> tuple[str, list[str]]:
    """One novel whose three chapters wear three different sync badges."""
    novel_id, (ankunft, abreise, heimkehr) = _seed_novel(
        novel_title, ["Ankunft", "Abreise", "Heimkehr"]
    )
    _seed_scenes(novel_id, ankunft, [_scene("Sturm")])
    _seed_scenes(novel_id, heimkehr, [_scene("Rückblick", "complete")])
    _seed_words(novel_id, heimkehr, "Erste Worte im Manuskript.")
    return novel_id, [ankunft, abreise, heimkehr]


def test_the_canvas_shows_columns_and_badges_in_german(page: Page, stack: Stack) -> None:
    novel_id, chapters = _seed_board("Die aufgestellte Bucht")
    ankunft_id = chapters[0]
    page.goto(f"{WEB_URL}/planning")
    page.get_by_role("link", name="Die aufgestellte Bucht").click()
    page.get_by_role("link", name="Storyboard öffnen").click()

    expect(page.get_by_role("heading", name="Storyboard")).to_be_visible()
    expect(page.get_by_role("heading", name="Exposition")).to_be_visible()
    expect(page.get_by_role("heading", name="Konfrontation")).to_be_visible()
    expect(page.get_by_role("heading", name="Auflösung")).to_be_visible()

    # The cards carry the title, the size and the sync badge — in German.
    ankunft = page.get_by_role("group", name="Ankunft")
    expect(ankunft.get_by_text("Geplant")).to_be_visible()
    abreise = page.get_by_role("group", name="Abreise")
    expect(abreise.get_by_text("Leer")).to_be_visible()
    heimkehr = page.get_by_role("group", name="Heimkehr")
    expect(heimkehr.get_by_text("Abgeschlossen")).to_be_visible()
    expect(heimkehr.get_by_text("4 Wörter")).to_be_visible()

    # The card's title walks to the chapter in the workspace.
    expect(ankunft.get_by_role("link", name="Ankunft")).to_have_attribute(
        "href", f"/novels/{novel_id}?chapter={ankunft_id}"
    )

    assert_accessible(page)


def test_a_move_through_the_menu_persists_across_a_reload(page: Page, stack: Stack) -> None:
    novel_id, _ = _seed_board("Die verschobene Bucht")
    page.goto(f"{WEB_URL}/planning/storyboard?novel={novel_id}")

    card = page.get_by_role("group", name="Ankunft")
    expect(card).to_be_visible()
    card.get_by_role("button", name="Ankunft in eine andere Phase verschieben").click()
    page.get_by_role("menuitem", name="Auflösung").click()

    # The card stands in its new column, and the server kept the move.
    auflösung = page.get_by_role("region", name="Auflösung")
    expect(auflösung.get_by_role("group", name="Ankunft")).to_be_visible()
    page.reload()
    moved = page.get_by_role("region", name="Auflösung")
    expect(moved.get_by_role("group", name="Ankunft")).to_be_visible()

    assert_accessible(page)


def test_a_drag_onto_another_stage_persists_across_a_reload(page: Page, stack: Stack) -> None:
    novel_id, _ = _seed_board("Die gezogene Bucht")
    page.goto(f"{WEB_URL}/planning/storyboard?novel={novel_id}")

    card = page.get_by_role("group", name="Ankunft")
    expect(card).to_be_visible()
    auflösung = page.get_by_role("region", name="Auflösung")
    card_handle = card.element_handle()
    target_handle = auflösung.element_handle()
    assert card_handle is not None and target_handle is not None
    with page.expect_response(
        lambda response: (
            response.request.method == "PUT" and response.url.endswith("/stage") and response.ok
        )
    ) as persisted:
        # Playwright's mouse-driven drag_to cannot carry an HTML5 DataTransfer,
        # so the drop rides the synthetic dragstart/dragover/drop sequence the
        # columns listen for — the dragstart handler fills the bag itself.
        page.evaluate(
            """([dragged, target]) => {
            const bag = new DataTransfer();
            dragged.dispatchEvent(
                new DragEvent("dragstart", { dataTransfer: bag, bubbles: true, cancelable: true }),
            );
            target.dispatchEvent(
                new DragEvent("dragover", { dataTransfer: bag, bubbles: true, cancelable: true }),
            );
            target.dispatchEvent(
                new DragEvent("drop", { dataTransfer: bag, bubbles: true, cancelable: true }),
            );
        }""",
            [card_handle, target_handle],
        )
    # The card's new column is optimistic; the reload must not race the PUT
    # that makes it the server's answer (the flake in #775).
    assert persisted.value.ok

    # The card stands in its new column, and the server kept the move.
    expect(auflösung.get_by_role("group", name="Ankunft")).to_be_visible()
    page.reload()
    moved = page.get_by_role("region", name="Auflösung")
    expect(moved.get_by_role("group", name="Ankunft")).to_be_visible()

    assert_accessible(page)


def test_the_remap_preview_confirms_onto_new_stages(page: Page, stack: Stack) -> None:
    novel_id, _ = _seed_board("Die umgestellte Bucht")
    page.goto(f"{WEB_URL}/planning/storyboard?novel={novel_id}")

    page.get_by_role("button", name="Strukturwechsel vorschauen").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("button", name="Heldenreise").click()

    # The preview names every move's before and after before anything writes.
    expect(dialog.get_by_text("Ankunft: Exposition → Gewohnte Welt")).to_be_visible()
    dialog.get_by_role("button", name="Übernehmen").click()

    # The canvas re-reads onto the new structure's columns.
    expect(page.get_by_role("heading", name="Gewohnte Welt")).to_be_visible()

    assert_accessible(page)


def test_the_canvas_fits_1280(page: Page, stack: Stack) -> None:
    """The storyboard fits a 1280 px desk viewport: no page-level sideways scroll."""
    novel_id, _ = _seed_board("Die kurze Aufstellung")
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(f"{WEB_URL}/planning/storyboard?novel={novel_id}")
    expect(page.get_by_role("heading", name="Storyboard")).to_be_visible()
    expect(page.get_by_role("group", name="Ankunft")).to_be_visible()

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
