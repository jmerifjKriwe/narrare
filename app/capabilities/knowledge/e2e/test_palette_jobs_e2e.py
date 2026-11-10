"""The palette's job rows: extraction and check behind lazy dialogs.

The mirror of the dock's job flows, entered through ⌘K instead of the tab:
the row opens the dialog already open, the trigger enqueues the same lane
the dock panels own, the row's state arrives through `JobStatus` — and a
refused enqueue is named in the dialog, never a silent close (unit-pinned;
here the lane answers). Both flows end on the accessibility floor with the
done row on screen.
"""

from datetime import datetime
from typing import TYPE_CHECKING

import httpx
import pytest
from playwright.sync_api import Page, expect

from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.stack import API_URL, WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

API = API_URL
BASE = WEB_URL

# The capitalized words steer the fake provider's extraction (one suggestion
# per name), the way the dock suite's body steers its five.
CHAPTER_BODY = "Mira betrat das alte Haus am See."

# The planted contradictions: two chapters give Mira and Tom two different
# ages each, one finding per name quoting both readings.
CONTRADICTING_BODIES = (
    "Mira ist 34, und Tom ist 30.",
    "Mira ist 37, und Tom ist 33.",
)


def _seed_chapter(client: httpx.Client, novel_id: str, body: str, title: str = "") -> str:
    """One chapter through the API, written and saved — what the jobs read; returns its id."""
    chapter = client.post(f"{API}/api/writing/novels/{novel_id}/chapters", json={"title": title})
    chapter.raise_for_status()
    written = client.put(f"{API}/api/writing/chapters/{chapter.json()['id']}", json={"body": body})
    written.raise_for_status()
    return str(chapter.json()["id"])


def _seed_novel(client: httpx.Client, title: str, bodies: tuple[str, ...]) -> str:
    """A novel with one chapter per body, through the API; returns its id."""
    novel = client.post(f"{API}/api/writing/novels", json={"title": title})
    novel.raise_for_status()
    novel_id = str(novel.json()["id"])
    for body in bodies:
        _seed_chapter(client, novel_id, body)
    return novel_id


def _open_palette(page: Page) -> None:
    """⌘K opens the palette over the workspace; the dialog answers."""
    page.keyboard.press("Control+k")
    palette = page.get_by_role("dialog", name="Befehlspalette")
    expect(palette).to_be_visible()


def _run_palette_command(page: Page, query: str, name: str) -> None:
    """Fill the palette, run the command row, land on its dialog."""
    _open_palette(page)
    palette = page.get_by_role("dialog", name="Befehlspalette")
    palette.get_by_role("textbox").fill(query)
    palette.get_by_role("group", name="Befehle").get_by_role("button", name=name).click()


def test_palette_runs_extraction_to_done(page: Page, stack: Stack) -> None:
    with httpx.Client(timeout=30) as client:
        novel_id = _seed_novel(client, "Die Palette der Bucht", (CHAPTER_BODY,))
    page.goto(f"{BASE}/novels/{novel_id}")
    expect(page.get_by_role("heading", name="Die Palette der Bucht")).to_be_visible()

    _run_palette_command(page, "Entitäten aus Kapitel", "Entitäten aus Kapitel extrahieren")
    dialog = page.get_by_role("dialog", name="Extraktion")
    expect(dialog).to_be_visible()
    trigger = dialog.get_by_role("button", name="Dieses Kapitel durchsuchen")
    trigger.click()
    expect(trigger).to_be_disabled()
    status = dialog.locator("[data-job-status]")
    expect(status).to_be_visible()
    expect(status).to_have_attribute("data-job-status", "done", timeout=60_000)
    expect(trigger).to_be_enabled()
    assert_accessible(page)


def test_palette_extraction_names_the_shown_chapter(page: Page, stack: Stack) -> None:
    """The palette's extraction names the chapter the workspace shows, not the fallback.

    Two titled chapters make the last-touched fallback differ from the open
    one: the workspace opens on the first chapter's address, the palette row
    runs, and the dialog names the first chapter — the same precedence the
    dock panel keeps. The trigger then runs that chapter's lane to done.
    """
    with httpx.Client(timeout=30) as client:
        novel = client.post(f"{API}/api/writing/novels", json={"title": "Die gezeigte Wahl"})
        novel.raise_for_status()
        novel_id = str(novel.json()["id"])
        shown_id = _seed_chapter(client, novel_id, CHAPTER_BODY, title="Erste Spur")
        latest_id = _seed_chapter(client, novel_id, CHAPTER_BODY, title="Zweite Spur")
        rows = client.get(f"{API}/api/writing/novels/{novel_id}/chapters")
        rows.raise_for_status()
        # The seeding order must leave the shown chapter off the fallback, or
        # the naming assertion below would pass vacuously.
        newest = max(rows.json(), key=lambda row: datetime.fromisoformat(row["updated_at"]))
        assert str(newest["id"]) == latest_id != shown_id
    page.goto(f"{BASE}/novels/{novel_id}?chapter={shown_id}")
    expect(page.get_by_role("heading", name="Die gezeigte Wahl")).to_be_visible()

    _run_palette_command(page, "Entitäten aus Kapitel", "Entitäten aus Kapitel extrahieren")
    dialog = page.get_by_role("dialog", name="Extraktion")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_text("Erste Spur")).to_be_visible()
    expect(dialog.get_by_text("Zweite Spur")).to_have_count(0)
    trigger = dialog.get_by_role("button", name="Dieses Kapitel durchsuchen")
    trigger.click()
    expect(trigger).to_be_disabled()
    status = dialog.locator("[data-job-status]")
    expect(status).to_be_visible()
    expect(status).to_have_attribute("data-job-status", "done", timeout=60_000)
    expect(trigger).to_be_enabled()
    assert_accessible(page)


def test_palette_runs_consistency_check_to_done(page: Page, stack: Stack) -> None:
    with httpx.Client(timeout=30) as client:
        novel_id = _seed_novel(client, "Die Palette der Prüfung", CONTRADICTING_BODIES)
    page.goto(f"{BASE}/novels/{novel_id}")
    expect(page.get_by_role("heading", name="Die Palette der Prüfung")).to_be_visible()

    _run_palette_command(page, "Ganzes Buch", "Ganzes Buch prüfen")
    dialog = page.get_by_role("dialog", name="Konsistenz")
    expect(dialog).to_be_visible()
    trigger = dialog.get_by_role("button", name="Ganzes Buch prüfen")
    trigger.click()
    expect(trigger).to_be_disabled()
    status = dialog.locator("[data-job-status]")
    expect(status).to_be_visible()
    expect(status).to_have_attribute("data-job-status", "done", timeout=60_000)
    expect(status).to_contain_text("2")
    expect(trigger).to_be_enabled()
    assert_accessible(page)
