"""The Szenen dock: scene plans beside the editor.

The tab is registry-driven: planning exports dockRoutes and the generated
registry carries the row, so the workspace renders the tab with zero
generator changes. Inside, the chapter's scenes render as an editable list
— title, status advance, add — and one save persists the whole list in
order; a reload proves the server kept it. At 1280 px with the rail
expanded the dock column scrolls internally while the page itself fits.
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

# The API the stack runs, for seeding a novel with scenes the way a user
# would build them — through the real service, no shortcuts.
API = API_URL


def _seed(novel_title: str, scenes: list[dict[str, str]]) -> str:
    """A novel with one chapter carrying the given scenes, through the API.

    The chapter is stored untitled, the way the rail's own create path
    stores it; the scene PUT is the same write the dock's save performs, so
    the seeding is a faster driver, not a shortcut around the product.
    Returns the novel's id, the workspace URL's parameter.
    """
    with httpx.Client(base_url=API, timeout=30) as api:
        novel = api.post("/api/writing/novels", json={"title": novel_title})
        novel.raise_for_status()
        novel_id = novel.json()["id"]
        chapter = api.post(f"/api/writing/novels/{novel_id}/chapters", json={"title": ""})
        chapter.raise_for_status()
        chapter_id = chapter.json()["id"]
        saved = api.put(
            f"/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes",
            json={"scenes": scenes},
        )
        saved.raise_for_status()
        assert [scene["position"] for scene in saved.json()["scenes"]] == list(
            range(1, len(scenes) + 1)
        )
    return novel_id


def _scene(title: str, status: str = "planned") -> dict[str, str]:
    return {"id": str(uuid4()), "title": title, "status": status}


def test_the_planning_dock_edits_and_saves_beside_the_editor(page: Page, stack: Stack) -> None:
    novel_id = _seed("Die geplante Bucht", [_scene("Anfang"), _scene("Mitte", "in_progress")])
    page.goto(f"{WEB_URL}/novels/{novel_id}")
    expect(page.get_by_role("heading", name="Die geplante Bucht")).to_be_visible()

    # The tab comes from the generated dock registry; the panel beside the
    # editor is the dock's own route rendering through the column's outlet.
    page.get_by_role("button", name="Szenen", exact=True).click()
    dock = page.get_by_role("complementary", name="Szenen")
    expect(dock).to_be_visible()
    expect(dock.get_by_role("heading", name="Szenenpläne")).to_be_visible()

    # A clean list stands its save down: nothing to write.
    save = dock.get_by_role("button", name="Szenen speichern")
    expect(save).to_be_disabled()

    # Edit the title and advance the status; both mark the list dirty, and
    # one save carries both to the server.
    dock.get_by_label("Titel von Szene 1").fill("Ankunft!")
    expect(dock.get_by_text("Ungespeicherte Änderungen.")).to_be_visible()
    expect(save).to_be_enabled()
    dock.get_by_role("group", name="Ankunft!").get_by_role(
        "button", name="Weiter zu In Arbeit"
    ).click()
    expect(
        dock.get_by_role("group", name="Ankunft!").get_by_text("In Arbeit", exact=True)
    ).to_be_visible()
    save.click()
    expect(dock.get_by_text("Ungespeicherte Änderungen.")).to_have_count(0)

    # Reload: the server kept the whole edit — the words and the status.
    page.reload()
    expect(dock).to_be_visible()
    expect(dock.get_by_label("Titel von Szene 1")).to_have_value("Ankunft!")
    expect(
        dock.get_by_role("group", name="Ankunft!").get_by_text("In Arbeit", exact=True)
    ).to_be_visible()
    expect(dock.get_by_label("Titel von Szene 2")).to_have_value("Mitte")

    # The dock's own words, in the suite's German: add, move and delete.
    expect(dock.get_by_role("button", name="Szene hinzufügen")).to_be_visible()
    expect(dock.get_by_role("button", name="Nach oben").first).to_be_visible()
    expect(dock.get_by_role("button", name="Szene löschen").first).to_be_visible()

    assert_accessible(page)


def test_the_planning_dock_scrolls_inside_its_column(page: Page, stack: Stack) -> None:
    """Fifty scenes stay inside the dock column at 1280 px.

    The rail stands expanded over the page — the desktop default — and the
    page itself fits the viewport: the column's own body scrolls under its
    title (`scrollHeight` past `clientHeight` allowed inside), while the
    document never grows past the window.
    """
    novel_id = _seed("Die lange Bucht", [_scene(f"Szene {n}") for n in range(1, 51)])
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(f"{WEB_URL}/novels/{novel_id}")
    expect(page.get_by_role("heading", name="Die lange Bucht")).to_be_visible()

    page.get_by_role("button", name="Szenen", exact=True).click()
    dock = page.get_by_role("complementary", name="Szenen")
    expect(dock).to_be_visible()
    expect(dock.get_by_role("group", name="Szene 50")).to_be_visible()

    # The column's scrollable body carries the overflow: the fifty rows do
    # not fit 800 px, and they must not try to.
    scroller = dock.locator(":scope > div")
    scroller_overflow = scroller.evaluate("element => element.scrollHeight - element.clientHeight")
    assert scroller_overflow > 0
    # The page itself fits: no document-level scroll in either axis.
    assert dock.evaluate("element => element.scrollWidth - element.clientWidth") <= 1
    page_overflow = page.evaluate(
        "document.documentElement.scrollHeight - document.documentElement.clientHeight"
    )
    assert page_overflow <= 1

    assert_accessible(page)
