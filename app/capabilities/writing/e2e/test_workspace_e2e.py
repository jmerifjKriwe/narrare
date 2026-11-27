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
    DATABASE,
    create_chapter,
    create_novel,
    patch_novel,
    patch_scene,
    set_daily_goal,
    set_theme,
    word_body,
    write_scene,
)
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.db_rows import rows
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
    # The knowledge interims retired (W5 #866/#867): the finding card and
    # the entity spotlight are gone — the knowledge region belongs to the
    # Wissen tab's face, and a closed dock owes no placeholder promise.
    # The atmosphere stays neutral (D21, #868).
    expect(page.get_by_text("Wird mit der Wissens-Welle aktiv")).to_have_count(0)
    expect(page.get_by_text("Fokussierte Entität")).to_have_count(0)
    # The dock's own tab (the rail's disabled Wissen door is a namesake).
    expect(
        page.get_by_role("group", name="Dock-Ansichten").get_by_role("button", name="Wissen")
    ).to_be_visible()

    # The chrome's book face: the breadcrumb names the route's book, the
    # word chip the book's own count, the rail's editor door current.
    topbar = page.locator("header")
    expect(topbar.get_by_role("link", name="Manuscripts")).to_have_attribute("href", "/")
    expect(topbar.get_by_text(KLANG)).to_be_visible()
    expect(topbar.get_by_text("1.855 Wörter")).to_be_visible()
    rail = page.get_by_role("navigation", name="Navigation")
    expect(rail.get_by_role("link", name="Editor")).to_have_attribute("aria-current", "page")

    # Every unbuilt door stays disabled with its note — the ribbon's
    # history/export (#875/#876) and the layout tune (#881); the ⌘J chip
    # carries its status mark (#869). The wiki door retired with #867
    # (W5 Task 2 — the dossier is the entity's expanded view, Tasks 3/5).
    # The CRUD doors are LIVE (Task 13) — the create suite drives them;
    # Fokus is LIVE (Task 18) — the zen suite drives it.
    for name in (
        "Verlauf",
        "Export",
        "Workspace-Layout",
    ):
        expect(page.get_by_role("button", name=name, exact=True)).to_be_disabled()
    for name in ("Neues Kapitel", "Neue Szene", "Fokus (F9)"):
        expect(page.get_by_role("button", name=name, exact=True)).to_be_enabled()
    expect(page.get_by_text("Noch nicht verfügbar.")).to_be_visible()

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


def test_the_book_settings_edit_the_real_family(page: Page, installed: Stack) -> None:
    """Task 19: the identity door opens the dialog on the real rows; the
    save carries the diff (target, status), the series create lands inline
    and the link + volume ride the save — the shelf's hero line speaks it.
    The dialog's inheritance note is true: this surface edits what setup
    bound."""
    novel = _seed_klang()
    patch_novel(str(novel["id"]), status="draft")
    _goto_workspace(page, str(novel["id"]))

    page.get_by_role("button", name="Buch-Einstellungen", exact=True).click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_role("heading", name="Buch-Einstellungen")).to_be_visible()
    expect(dialog.get_by_label("Romantitel", exact=True)).to_have_value(KLANG)
    expect(dialog.get_by_label("Autor", exact=True)).to_have_value(AUTHOR)
    expect(dialog.get_by_label("Zielumfang (Wörter gesamt)", exact=True)).to_have_value("85.000")
    expect(dialog.get_by_role("radio", name="Entwurf", exact=True)).to_have_attribute(
        "aria-checked", "true"
    )
    # The atelier section retired (W7): the profile's fields live on
    # /settings — the retired section's door stands in its place.
    expect(dialog.get_by_role("button", name="Profil in den Einstellungen öffnen")).to_be_visible()

    # The diff rides the save — the target and the status change.
    dialog.get_by_label("Zielumfang (Wörter gesamt)", exact=True).fill("90000")
    dialog.get_by_role("radio", name="Überarbeitung", exact=True).click()
    dialog.get_by_role("button", name="Speichern", exact=True).click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    # The dock's planned length reads the new target.
    expect(page.get_by_text("90.000 W.")).to_be_visible()

    # Reopen — the stored answers stand, the series create lands inline.
    page.get_by_role("button", name="Buch-Einstellungen", exact=True).click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_label("Zielumfang (Wörter gesamt)", exact=True)).to_have_value("90.000")
    expect(dialog.get_by_role("radio", name="Überarbeitung", exact=True)).to_have_attribute(
        "aria-checked", "true"
    )
    dialog.get_by_role("button", name="Neue Reihe anlegen", exact=True).click()
    dialog.get_by_label("Name der neuen Reihe", exact=True).fill("Tiefsee-Chroniken")
    dialog.get_by_role("button", name="Anlegen", exact=True).click()
    series_select = dialog.get_by_label("Zugehörige Buchreihe", exact=True)
    expect(series_select.locator("option:checked")).to_have_text("Tiefsee-Chroniken")
    dialog.get_by_label("Band", exact=True).fill("2")
    dialog.get_by_role("button", name="Speichern", exact=True).click()
    expect(page.get_by_role("dialog")).to_have_count(0)

    # The shelf's hero series line speaks the link and the volume.
    page.goto(BASE + "/")
    expect(page.get_by_text("Tiefsee-Chroniken, Band 2")).to_be_visible()
    assert_accessible(page)


def test_the_inline_goal_setters_write_the_real_rows(page: Page, installed: Stack) -> None:
    """Task 19, D20: the ring's affordance writes the atelier's daily goal
    (the ring reads it back), the pill's writes the chapter's own target
    (the pair and the fill read it back)."""
    novel = _seed_klang()
    _goto_workspace(page, str(novel["id"]))

    # The daily goal: 2.000 → 2.500, the ring's pair follows.
    ring = page.get_by_test_id("explorer-ring")
    ring.get_by_role("button", name="Tagesziel anpassen", exact=True).click()
    goal = page.get_by_role("dialog")
    expect(goal.get_by_label("Tagesziel (Wörter)", exact=True)).to_have_value("2.000")
    goal.get_by_label("Tagesziel (Wörter)", exact=True).fill("2500")
    goal.get_by_role("button", name="Speichern", exact=True).click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(page.get_by_text("1.855 / 2.500 W.")).to_be_visible()

    # The chapter goal: the neutral „—" becomes the real pair and fill.
    ribbon = page.get_by_test_id("workspace-ribbon")
    ribbon.get_by_role("button", name="Kapitelziel anpassen", exact=True).click()
    goal = page.get_by_role("dialog")
    goal.get_by_label("Kapitelziel (Wörter)", exact=True).fill("1000")
    goal.get_by_role("button", name="Speichern", exact=True).click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(ribbon.get_by_text("765 / 1.000 Wörter")).to_be_visible()
    assert_accessible(page)


def test_the_dark_book_settings_clear_the_axe_floor(page: Page, installed: Stack) -> None:
    """The dialog on the tokens' dark halves — the same WCAG A/AA floor
    the workspace rides, with the form open."""
    set_theme("dark")
    novel = _seed_klang()
    _goto_workspace(page, str(novel["id"]))
    page.get_by_role("button", name="Buch-Einstellungen", exact=True).click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_role("heading", name="Buch-Einstellungen")).to_be_visible()
    assert_accessible(page)


def test_the_light_book_settings_clear_the_axe_floor(page: Page, installed: Stack) -> None:
    """The dialog's light face with the form open — the same WCAG A/AA floor
    the dark face rides (Task 21's fidelity gate, both themes)."""
    novel = _seed_klang()
    _goto_workspace(page, str(novel["id"]))
    page.get_by_role("button", name="Buch-Einstellungen", exact=True).click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_role("heading", name="Buch-Einstellungen")).to_be_visible()
    assert_accessible(page)


def test_the_settings_save_lands_on_the_db_rows(page: Page, installed: Stack) -> None:
    """Task 21's fidelity gate, W7's split: the dialog's save is not a UI
    echo — it lands on the real rows. The status, target and per-book
    author ride the novel PATCH; the series create lands its own user-owned
    row and the link + volume ride the novel. The atelier's author name and
    daily goal retired from the dialog (W7): they walk the settings surface
    through the dialog's own door, at the profile section's address, and
    land on the users row there. Every field is read back from Postgres,
    not the form."""
    novel = _seed_klang()
    novel_id = str(novel["id"])
    patch_novel(novel_id, status="draft")
    _goto_workspace(page, novel_id)

    page.get_by_role("button", name="Buch-Einstellungen", exact=True).click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_role("heading", name="Buch-Einstellungen")).to_be_visible()

    # The novel's own fields: author, target, status.
    dialog.get_by_label("Autor", exact=True).fill("M. Reyes")
    dialog.get_by_label("Zielumfang (Wörter gesamt)", exact=True).fill("90000")
    dialog.get_by_role("radio", name="Überarbeitung", exact=True).click()

    # The series create lands inline, the link and volume ride the save.
    dialog.get_by_role("button", name="Neue Reihe anlegen", exact=True).click()
    dialog.get_by_label("Name der neuen Reihe", exact=True).fill("Tiefsee-Chroniken")
    dialog.get_by_role("button", name="Anlegen", exact=True).click()
    expect(
        dialog.get_by_label("Zugehörige Buchreihe", exact=True).locator("option:checked")
    ).to_have_text("Tiefsee-Chroniken")
    dialog.get_by_label("Band", exact=True).fill("2")

    dialog.get_by_role("button", name="Speichern", exact=True).click()
    expect(page.get_by_role("dialog")).to_have_count(0)

    # The novel row: the diff landed, the series link and volume with it.
    novel_row = rows(
        DATABASE,
        "SELECT status, target_words, author, series_id, series_volume FROM novels WHERE id = :id",
        {"id": novel_id},
    )
    assert len(novel_row) == 1
    status, target_words, author, series_id, series_volume = novel_row[0]
    assert status == "revision"
    assert target_words == 90000
    assert author == "M. Reyes"
    assert series_id is not None
    assert series_volume == 2

    # The series row: created, user-owned (rule 4), named as the dialog asked.
    series_row = rows(
        DATABASE,
        "SELECT title, user_id FROM series WHERE id = :id",
        {"id": str(series_id)},
    )
    assert series_row == [("Tiefsee-Chroniken", LOCAL_USER_ID)]

    # The profile (W7): the dialog's door routes to the settings surface at
    # the profile section's address — the landing is the name field — and
    # the atelier's author name and daily goal land on the users row there.
    page.get_by_role("button", name="Buch-Einstellungen", exact=True).click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("button", name="Profil in den Einstellungen öffnen").click()
    expect(page).to_have_url(re.compile(r"/settings#profil-sektion"))
    author_name = page.get_by_label("Autorenname", exact=True)
    expect(author_name).to_be_focused()
    author_name.fill("M. Reyes Atelier")
    page.get_by_label("Tagesziel (Wörter)", exact=True).fill("2500")
    page.get_by_role("button", name="Änderungen speichern", exact=True).click()
    # The saved truth stands in the fields: the dirty badge retires once the
    # invalidated row answered, and the goal reads back the grouped figure —
    # the local PATCH answers inside one frame, so a busy-window wait would
    # race it.
    expect(page.get_by_text("Ungespeicherte Eingaben")).to_have_count(0)
    expect(page.get_by_label("Tagesziel (Wörter)", exact=True)).to_have_value("2.500")

    # The atelier row: the profile's author name and the daily goal landed.
    user_row = rows(
        DATABASE,
        "SELECT author_name, daily_goal_words FROM users WHERE id = :id",
        {"id": LOCAL_USER_ID},
    )
    assert user_row == [("M. Reyes Atelier", 2500)]
