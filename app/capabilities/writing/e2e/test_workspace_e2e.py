"""The workspace reads the real stack (W4 Task 11): browser, API, Postgres.

Every test opens on a freshly installed instance (``e2e/conftest.py``) and
seeds exactly the population it asserts on through the writing API. The
read-only workspace renders the rows' own facts — the scene tree with its
tabular word counts, the last-edited active scene, the written-out scene
header, the daily ring from the activity aggregate, the tension card's
stage label from planning's storyboard, the dock's real cover miniature —
and every door the further build-out has not reached stays disabled with
its note (the CRUD doors went live in Task 13 — their own suite drives
them). The shelf hero's door resumes the last-edited scene and names
chapter + scene honestly (gap row 3); the empty book and empty chapter
answer per the states sheet; a deleted book degrades to the shelf with the
note; the dark face clears the same axe WCAG A/AA floor the shelf rides.
"""

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.capabilities.writing.e2e.conftest import (
    create_chapter,
    create_novel,
    patch_novel,
    patch_scene,
    set_daily_goal,
    set_theme,
    word_body,
    write_scene,
)
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.stack import WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = WEB_URL

KLANG = "Der Klang des Eises"
KLANG_GENRE = "Mystery & Noir"
AUTHOR = "H. Calder"
SHELF_TITLE = "Das Bücherregal"
EMPTY_BOOK_TITLE = "Ein unbeschriebenes Werk"
EMPTY_CHAPTER_TITLE = "Erste Szene starten"
DELETED_NOTE = "Das Buch wurde anderswo gelöscht — das Regal zeigt den aktuellen Stand."


def _seed_klang() -> dict[str, object]:
    """The draft's populated book, on real rows: two chapters, three scenes
    (342 + 1.090 + 423 words — the last-created scene is chapter 1's second,
    so the last-edited rule opens the workspace on „Das Signal im
    Permafrost"), the book's author and target, the atelier's daily goal."""
    novel = create_novel(KLANG, genre=KLANG_GENRE, target_words=85000)
    patch_novel(str(novel["id"]), author=AUTHOR)
    chapter1 = create_chapter(str(novel["id"]), "Der erste Schnee")
    chapter2 = create_chapter(str(novel["id"]), "Nevada Echoes")
    write_scene(str(chapter1["id"]), word_body(342), title="An Bord der Vanguard")
    write_scene(str(chapter2["id"]), word_body(1090), title="Sub-Basement")
    write_scene(
        str(chapter1["id"]),
        word_body(423),
        title="Das Signal im Permafrost",
        setting="Forschungsstation 7",
        story_time="27. Oktober 2094, 03:14 UTC",
    )
    set_daily_goal(2000)
    return novel


def _goto_workspace(page: Page, novel_id: str) -> None:
    page.goto(f"{BASE}/novels/{novel_id}")
    # The ready-state surface, not any h1 — the loading skeleton carries an
    # sr-only heading Playwright counts as visible (a 1x1 box).
    expect(
        page.get_by_test_id("explorer-tree").or_(page.get_by_test_id("explorer-empty-book"))
    ).to_be_visible()


def test_the_workspace_reads_the_seeded_book(page: Page, installed: Stack) -> None:
    """The three columns on the rows' own data, the chrome's book face, the
    hero door's resume — and every unbuilt door honestly disabled."""
    novel = _seed_klang()
    novel_id = str(novel["id"])

    # The shelf hero's door names the last-edited chapter + scene (row 3).
    page.goto(BASE + "/")
    door = page.get_by_role("link", name="Weiterschreiben — Kapitel 1 · Szene 2")
    expect(door).to_have_attribute("href", f"/novels/{novel_id}")
    door.click()
    expect(page).to_have_url(f"{BASE}/novels/{novel_id}")

    # The editor opens on the last-edited scene — the draft's anatomy, the
    # row's own figures: written-out eyebrow, overline, running head, prose,
    # foot. No folio, no page count (row 9).
    expect(page.get_by_role("heading", name="Das Signal im Permafrost", exact=True)).to_be_visible()
    expect(page.get_by_text("Kapitel Eins · Szene Zwei")).to_be_visible()
    expect(page.get_by_text("Forschungsstation 7 · 27. Oktober 2094, 03:14 UTC")).to_be_visible()
    expect(page.get_by_text(f"{KLANG} — {AUTHOR}")).to_be_visible()
    expect(page.get_by_text("423 Wörter im Gesamtabschnitt")).to_be_visible()
    expect(page.get_by_text("Automatisch gesichert")).to_be_visible()
    expect(page.get_by_test_id("workspace-ribbon").get_by_text("K1-S2")).to_be_visible()
    expect(page.get_by_text(re.compile("Seite .* von"))).to_have_count(0)

    # The tree: chapters and scenes in position order, tabular counts, the
    # active marker on the last-edited scene, neutral dots elsewhere (#873).
    expect(page.get_by_text("Kapitel 1 — Der erste Schnee")).to_be_visible()
    expect(page.get_by_text("Kapitel 2 — Nevada Echoes")).to_be_visible()
    expect(page.get_by_text("Szene 1 · An Bord der Vanguard")).to_be_visible()
    expect(page.get_by_text("Szene 1 · Sub-Basement")).to_be_visible()
    expect(page.get_by_text("765 W.")).to_be_visible()
    expect(page.get_by_text("Gesamt: 1.855 W.")).to_be_visible()
    active = page.get_by_role("button", name=re.compile("Szene 2 · Das Signal im Permafrost"))
    expect(active).to_have_attribute("aria-current", "true")

    # The ring reads the aggregate (1.855 today over the 2.000 goal), the
    # tension card the storyboard's own stage label (chapter 1 sits at the
    # three-act structure's setup — „Exposition"), the codes the rows' own.
    expect(page.get_by_text("1.855 / 2.000 W.")).to_be_visible()
    expect(page.get_by_text("92 %")).to_be_visible()
    expect(page.get_by_text("Noch 145 Wörter bis zum Etappenziel")).to_be_visible()
    expect(page.get_by_text("Exposition")).to_be_visible()
    expect(page.get_by_text("K1-S1")).to_be_visible()
    expect(page.get_by_text("K2-S1")).to_be_visible()

    # The dock's one real card: the cover miniature, target, count, progress.
    expect(page.get_by_text("2 % Gesamt")).to_be_visible()
    expect(page.get_by_text("Geplante Länge:")).to_be_visible()
    expect(page.get_by_text("85.000 W.")).to_be_visible()
    expect(page.get_by_text("Erfasst: 1.855 Wörter")).to_be_visible()
    # The neutrals stay neutral (D21): finding, entity, atmosphere.
    expect(page.get_by_text("Keine offenen Brüche")).to_be_visible()
    expect(page.get_by_text("Wird mit der Wissens-Welle aktiv")).to_be_visible()

    # The chrome's book face: the breadcrumb names the route's book, the
    # word chip the book's own count, the rail's editor door current.
    topbar = page.locator("header")
    expect(topbar.get_by_role("link", name="Manuscripts")).to_have_attribute("href", "/")
    expect(topbar.get_by_text(KLANG)).to_be_visible()
    expect(topbar.get_by_text("1.855 Wörter")).to_be_visible()
    rail = page.get_by_role("navigation", name="Navigation")
    expect(rail.get_by_role("link", name="Editor")).to_have_attribute("aria-current", "page")

    # Every unbuilt door stays disabled with its note — the ribbon's
    # focus/history/export (#875/#876), the wiki (#867), the layout tune
    # (#881); the ⌘J chip carries its „bald" mark (#869). The CRUD doors
    # are LIVE (Task 13) — the create suite drives them.
    for name in (
        "Verlauf",
        "Export",
        "Fokus (F9)",
        "Wiki öffnen",
        "Workspace-Layout",
    ):
        expect(page.get_by_role("button", name=name, exact=True)).to_be_disabled()
    for name in ("Neues Kapitel", "Neue Szene"):
        expect(page.get_by_role("button", name=name, exact=True)).to_be_enabled()
    expect(page.get_by_text("bald")).to_be_visible()

    # Selecting another scene moves the editor and the marker — read-only
    # navigation, no write.
    page.get_by_role("button", name=re.compile("Szene 1 · Sub-Basement")).click()
    expect(page.get_by_role("heading", name="Sub-Basement", exact=True)).to_be_visible()
    # The code now stands in the ribbon AND the tension label row.
    expect(page.get_by_text("K2-S1").first).to_be_visible()
    expect(page.get_by_role("button", name=re.compile("Szene 1 · Sub-Basement"))).to_have_attribute(
        "aria-current", "true"
    )
    expect(active).not_to_have_attribute("aria-current", "true")

    assert_accessible(page)


def test_the_empty_book_and_empty_chapter_faces(page: Page, installed: Stack) -> None:
    """The states sheet's Kacheln 3 and 4: the invitation and the first-scene
    explanation, their create doors live (Task 13 — the create suite drives
    the full flow; here the faces stand on the seeded rows)."""
    novel = create_novel("Leeres Buch")
    novel_id = str(novel["id"])

    _goto_workspace(page, novel_id)
    expect(page.get_by_role("heading", name=EMPTY_BOOK_TITLE)).to_be_visible()
    expect(page.get_by_text("Noch keine Kapitel")).to_be_visible()
    expect(page.get_by_text("Beginne mit dem ersten Kapitel deines Romans.")).to_be_visible()
    expect(page.get_by_role("button", name="+ Erstes Kapitel anlegen")).to_be_enabled()
    # The book is real, only empty: identity card and dock stand.
    expect(page.get_by_text("Leeres Buch").first).to_be_visible()
    expect(page.get_by_text("Erfasst: 0 Wörter")).to_be_visible()
    assert_accessible(page)

    # A chapter with zero scenes is D16's real state — the tree says so,
    # the editor explains the scene, the create door stands ready.
    create_chapter(novel_id, "Erstes Kapitel")
    page.reload()
    expect(page.get_by_role("heading", name=EMPTY_CHAPTER_TITLE)).to_be_visible()
    expect(page.get_by_text("Eine Szene ist der Ort, an dem du schreibst.")).to_be_visible()
    expect(page.get_by_text("Keine Szenen angelegt")).to_be_visible()
    expect(page.get_by_role("button", name="+ Szene 1 anlegen")).to_be_enabled()
    assert_accessible(page)


def test_the_door_resumes_the_last_edited_scene(page: Page, installed: Stack) -> None:
    """Row 3's rule end to end: a body touch advances updated_at, the door's
    label follows, and the workspace opens on the touched scene."""
    novel = create_novel(KLANG, genre=KLANG_GENRE)
    novel_id = str(novel["id"])
    chapter1 = create_chapter(novel_id, "Der erste Schnee")
    chapter2 = create_chapter(novel_id, "Nevada Echoes")
    first = write_scene(str(chapter1["id"]), word_body(10), title="An Bord der Vanguard")
    write_scene(str(chapter2["id"]), word_body(20), title="Sub-Basement")

    # The last-created scene leads — chapter 2's first.
    page.goto(BASE + "/")
    expect(page.get_by_role("link", name="Weiterschreiben — Kapitel 2 · Szene 1")).to_be_visible()

    # A touch on chapter 1's scene advances its updated_at — the door follows.
    patch_scene(str(first["id"]), body=word_body(15))
    page.reload()
    door = page.get_by_role("link", name="Weiterschreiben — Kapitel 1 · Szene 1")
    expect(door).to_be_visible()
    door.click()
    expect(page).to_have_url(f"{BASE}/novels/{novel_id}")
    expect(page.get_by_role("heading", name="An Bord der Vanguard", exact=True)).to_be_visible()
    touched = page.get_by_role("button", name=re.compile("Szene 1 · An Bord der Vanguard"))
    expect(touched).to_have_attribute("aria-current", "true")
    assert_accessible(page)


def test_a_deleted_book_degrades_to_the_shelf_with_the_note(page: Page, installed: Stack) -> None:
    """The 404 degrade: the workspace never shows a dead book — the shelf
    answers with the current truth and the one-shot note."""
    create_novel(KLANG)
    page.goto(f"{BASE}/novels/00000000-0000-0000-0000-000000000000")
    expect(page).to_have_url(BASE + "/")
    expect(page.get_by_role("heading", name=SHELF_TITLE)).to_be_visible()
    expect(page.get_by_text(DELETED_NOTE)).to_be_visible()
    # The note is one-shot: a reload does not carry it.
    page.reload()
    expect(page.get_by_role("heading", name=SHELF_TITLE)).to_be_visible()
    expect(page.get_by_text(DELETED_NOTE)).to_have_count(0)
    assert_accessible(page)


def test_the_dark_workspace_face_clears_the_axe_floor(page: Page, installed: Stack) -> None:
    """Spec 11: the settings row's dark theme, adopted at boot — the
    workspace renders on the tokens' dark halves and clears the axe floor."""
    set_theme("dark")
    novel = _seed_klang()
    _goto_workspace(page, str(novel["id"]))
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(22, 20, 15)"
    expect(page.get_by_role("heading", name="Das Signal im Permafrost", exact=True)).to_be_visible()
    expect(page.get_by_text("1.855 / 2.000 W.")).to_be_visible()
    assert_accessible(page)
