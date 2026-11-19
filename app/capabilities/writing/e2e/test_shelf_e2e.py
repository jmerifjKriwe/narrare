# The German face's own quotes and dashes are the catalog text these tests
# assert literally — intentional characters, not confusable typos.
# ruff: noqa: RUF001
"""The shelf drives the real stack: browser, API and Postgres.

Every shelf test opens on a freshly installed, empty instance
(``e2e/conftest.py`` empties the database, completes setup through the real
API and retires the setup's own novel), then seeds exactly the population it
asserts on through the writing API. The rendered figures are the rows' own —
word pairs, chapter counts, genres, statuses, the hero's last-edited lead —
and the database assertions are the honest check: the screen and the row
must agree. Search answers titles, genre components and figures by equality;
the facets compose OR within a group and AND across; duplicate copies the
whole book; export lands a real ZIP and stamps the menu; archive leaves and
returns through the drafted confirm; the hero's own menu archives the hero
and the next active book leads (#863); the new-book dialog creates the hero
with a neutral word stand and the atelier's inherited answers — the setup
book standing as their source — while the empty-shelf door creates with
honest NULLs when no source remains; an API chapter write moves the banner
through the shelf's own invalidation seam — without a reload; the banner's
goal line reads the atelier's daily goal (W4 row 25): the unset neutral,
the open remainder and the reached done-copy, never the hero book's pin;
the pre-setup gate hands `/` to the welcome and the inverse gate hands `/setup` back; the
app-wide chrome frames the shelf (W4 Task 10, D15/D17): the rail's nav and
real book-switcher menu, the topbar's breadcrumb, word total, interim save
chip, disabled ⌘K chip (#882), the language chip as the real switcher, the
tri-state theme toggle and the user block's author_name → email fallback; and
the dark face clears the same axe WCAG A/AA floor the setup suite rides
(``assert_accessible``).
"""

import json
import re
import zipfile
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.capabilities.writing.e2e.conftest import (
    DATABASE,
    SETUP_ANSWERS,
    create_chapter,
    create_novel,
    get_activity,
    get_novel,
    patch_novel,
    set_author_name,
    set_daily_goal,
    set_theme,
    word_body,
    write_scene,
)
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.db_rows import rows as _shared_rows
from app.kernel.testing.stack import WEB_URL

if TYPE_CHECKING:
    from pathlib import Path

    from playwright.sync_api import Locator

    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = WEB_URL

# The shelf's German face (de-DE context, pinned in app/capabilities/conftest.py).
SHELF_TITLE = "Das Bücherregal"
HERO_EYEBROW = "Aktuell in Arbeit"
NEW_BOOK = "Neues Buch anlegen"
SEARCH_LABEL = "Titel, Genres oder Zahlen suchen..."
FILTER_TITLE = "Filtern"
CARD_OPTIONS = "Projekt-Optionen"
MENU_TITLE = "Buch-Optionen"
MENU_ARCHIVED = "Archivierte Optionen"
CONFIRM_TITLE = "Ins Archiv stellen?"
ARCHIVE_SWITCH = "Archiv einbeziehen"
ARCHIVED_PILL = "Archiviert"
LAST_EXPORT = "Letzter Export:"
ARCHIVED_AT = "Archiviert am:"
SEARCH_EMPTY_TITLE = "Kein Buch passt zu deiner Suche."
SEARCH_EMPTY_CLEAR = "Suche und Filter zurücksetzen"
BANNER_NEUTRAL = (
    "Noch keine Schreibaktivität — der erste Schreibtag beginnt mit dem ersten Kapitel."
)
DIALOG_TITLE = "Neues Werk aufschlagen"
TITLE_LABEL = "Arbeitstitel des Manuskripts"
TITLE_MISSING = "Ein Arbeitstitel fehlt noch — er trägt dein Werk bis zur ersten Seite."
WORDS_LABEL = "Ziel-Umfang des Manuskripts"
CREATE = "Anlegen"
INHERITANCE_NOTE = (
    "Dramaturgie, KI-Rolle und Kanon-Strenge übernimmt das Buch aus deinen "
    "Atelier-Einstellungen — änderbar, sobald der Workspace da ist."
)
EMPTY_TITLE = "Dein erstes Buch wartet."
WELCOME_HEADING = "Tritt ein. Dein ungeschriebenes Werk wartet."

# The seeded population's own facts — the figures the shelf must render.
KLANG = "Der Klang des Eises"
KLANG_GENRE = "Mystery & Noir"
KLANG_BLURB = "Eine Spur im ewigen Eis, die nicht schmilzt."
GAERTNERIN = "Die Gärtnerin von Lyon"
WINTERHAUS = "Winterhaus"
COPY_TITLE = '„Der Klang des Eises (Kopie)"'


def _rows(statement: str, params: dict[str, object] | None = None) -> list[tuple[object, ...]]:
    """Thin wrapper over the shared reader (app/kernel/testing/db_rows)."""
    return _shared_rows(DATABASE, statement, params)


def _goto_shelf(page: Page) -> None:
    page.goto(BASE + "/")
    expect(page.get_by_role("heading", name=SHELF_TITLE)).to_be_visible()


def _hero(page: Page) -> Locator:
    """The hero panel — the section wearing the „Aktuell in Arbeit" eyebrow."""
    return page.locator("section").filter(has=page.get_by_text(HERO_EYEBROW, exact=True))


def _banner(page: Page) -> Locator:
    """The activity banner — the section wearing the „Wochenschnitt" eyebrow."""
    return page.locator("section").filter(has=page.get_by_text("Wochenschnitt", exact=True))


def _metric(page: Page, label: str) -> Locator:
    """One quick-metrics chip: the label's parent carries value and label."""
    return page.get_by_text(label, exact=True).locator("..")


def _card(page: Page, title: str) -> Locator:
    """One grid card — the article whose heading is exactly the book's title."""
    return page.get_by_role("article").filter(
        has=page.get_by_role("heading", name=title, exact=True)
    )


def _open_card_menu(page: Page, title: str, *, archived: bool = False) -> Locator:
    _card(page, title).get_by_role("button", name=CARD_OPTIONS).click()
    menu = page.get_by_role("dialog", name=MENU_ARCHIVED if archived else MENU_TITLE)
    expect(menu).to_be_visible()
    return menu


def _archive_through_confirm(page: Page, title: str) -> None:
    """The drafted archive path: menu → confirm → the confirm's own action."""
    menu = _open_card_menu(page, title)
    menu.get_by_role("button", name="Archivieren").click()
    confirm = page.get_by_role("dialog", name=CONFIRM_TITLE)
    expect(confirm).to_be_visible()
    confirm.get_by_role("button", name="Archivieren", exact=True).click()


def _seed_klang_with_chapter(words: int) -> dict[str, object]:
    """The rich book: genre, blurb, target and one written chapter."""
    novel = create_novel(KLANG, genre=KLANG_GENRE, blurb=KLANG_BLURB, target_words=80000)
    chapter = create_chapter(str(novel["id"]), "Der erste Schnee")
    write_scene(str(chapter["id"]), word_body(words))
    return novel


def test_the_shelf_renders_the_rows_own_facts(page: Page, installed: Stack) -> None:
    """Spec 1: titles, genres and word pairs from the seeded rows; the hero is
    the latest-edited book, the grid the rest newest first; a book without a
    target keeps the honest neutral. The rows below are the honest check."""
    create_novel(GAERTNERIN, genre="Historischer Roman", target_words=50000)
    create_novel(WINTERHAUS)
    _seed_klang_with_chapter(1200)
    # The atelier's daily goal (W4 row 25) — the banner reads the user's
    # answer, not the hero book's target: 2.000 stored, 1.200 written.
    set_daily_goal(2000)

    _goto_shelf(page)
    expect(page).to_have_title(f"{SHELF_TITLE} — Narrare")

    # The hero: the chapter write advanced Klang's updated_at last, so it leads.
    hero = _hero(page)
    expect(hero).to_be_visible()
    expect(page.get_by_role("heading", name=KLANG, exact=True)).to_be_visible()
    expect(hero.get_by_text(KLANG_GENRE, exact=True)).to_be_visible()
    expect(hero.get_by_text(KLANG_BLURB, exact=True)).to_be_visible()
    expect(hero.get_by_text("1.200", exact=True)).to_be_visible()
    expect(hero.get_by_text("/ 80.000 Wörter", exact=True)).to_be_visible()
    expect(hero.get_by_text("1", exact=True)).to_be_visible()
    expect(hero.get_by_text("Kapitel", exact=True)).to_be_visible()
    expect(hero.get_by_text("1 %", exact=True)).to_be_visible()
    expect(hero).to_contain_text("Zuletzt bearbeitet:")

    # The grid: the rest, newest first — Winterhaus (no genre, no target)
    # before Gärtnerin; the neutral is the count alone and a dash.
    cards = page.get_by_role("article")
    expect(cards).to_have_count(2)
    expect(cards.nth(0)).to_contain_text(WINTERHAUS)
    expect(cards.nth(1)).to_contain_text(GAERTNERIN)
    winter = _card(page, WINTERHAUS)
    expect(winter.get_by_text("0 Wörter", exact=True)).to_be_visible()
    expect(winter.get_by_text("—", exact=True)).to_be_visible()
    gaertnerin = _card(page, GAERTNERIN)
    expect(gaertnerin).to_contain_text("Historischer Roman")
    expect(gaertnerin.get_by_text("0 / 50.000 Wörter", exact=True)).to_be_visible()
    expect(gaertnerin.get_by_text("0 Kapitel", exact=True)).to_be_visible()
    expect(gaertnerin.get_by_text("0 %", exact=True)).to_be_visible()

    # The metrics strip and the banner read the same rows. The banner's
    # goal line is the daily goal — the hero-book pin ended (row 25); the
    # hero panel above keeps the book's own pair.
    expect(_metric(page, "Aktive Projekte")).to_contain_text("3 Romane")
    expect(_metric(page, "Gesamtwörter")).to_contain_text("1.200")
    expect(_metric(page, "Schreibstreak")).to_contain_text("1 Tag")
    banner = _banner(page)
    expect(banner).to_contain_text("Heutiges Schreibziel: 2.000 Wörter")
    expect(banner).to_contain_text("Du hast heute bereits 1.200 Wörter verfasst.")
    expect(banner).to_contain_text("Noch 800 Wörter bis zum Tagesziel.")
    expect(banner).not_to_contain_text("Ziel für")
    expect(banner.get_by_text("40,0 W/Tag", exact=True)).to_be_visible()
    assert_accessible(page)

    # The honest check: the rows carry exactly what the shelf rendered.
    assert _rows("SELECT title, genre, target_words FROM novels ORDER BY created_at") == [
        (GAERTNERIN, "Historischer Roman", 50000),
        (WINTERHAUS, None, None),
        (KLANG, KLANG_GENRE, 80000),
    ]
    assert _rows("SELECT title FROM chapters") == [("Der erste Schnee",)]
    assert _rows("SELECT SUM(words) FROM daily_words") == [(1200,)]
    assert _rows("SELECT daily_goal_words FROM users") == [(2000,)]


def test_search_answers_titles_genres_and_figures(page: Page, installed: Stack) -> None:
    """Spec 2: the whole trimmed query, case-insensitive — a substring of the
    title or a genre component, a figure by EQUALITY against word or chapter
    count (never a substring of the count), and still text beside. The hero
    is the shelf's fixed lead and never hides."""
    _seed_klang_with_chapter(1200)
    create_novel(GAERTNERIN, genre="Historischer Roman", target_words=50000)
    create_novel("Station 7", genre="Science Fiction & Speculative")
    create_novel(WINTERHAUS)  # created last → the hero; the grid holds the rest

    _goto_shelf(page)
    search = page.get_by_role("textbox", name=SEARCH_LABEL)
    results = page.get_by_role("status")
    expect(page.get_by_role("article")).to_have_count(3)

    # Title substring, case-insensitive.
    search.fill("KLANG")
    expect(_card(page, KLANG)).to_be_visible()
    expect(page.get_by_role("article")).to_have_count(1)
    expect(results).to_have_text("1 Buch gefunden")
    expect(page.get_by_role("heading", name=WINTERHAUS, exact=True)).to_be_visible()

    # A genre component answers too.
    search.fill("noir")
    expect(page.get_by_role("article")).to_have_count(1)
    expect(_card(page, KLANG)).to_be_visible()

    # Figures: plain and thousands-grouped, by equality on the word count.
    search.fill("1200")
    expect(page.get_by_role("article")).to_have_count(1)
    expect(_card(page, KLANG)).to_be_visible()
    search.fill("1.200")
    expect(page.get_by_role("article")).to_have_count(1)
    expect(_card(page, KLANG)).to_be_visible()

    # Equality on the chapter count; and a figure still searches text.
    search.fill("1")
    expect(page.get_by_role("article")).to_have_count(1)
    expect(_card(page, KLANG)).to_be_visible()
    search.fill("7")
    expect(page.get_by_role("article")).to_have_count(1)
    expect(_card(page, "Station 7")).to_be_visible()

    # Equality, never substring: „12" is no part of 1200 — the honest empty
    # search panel answers, the hero still stands.
    search.fill("12")
    expect(page.get_by_role("article")).to_have_count(0)
    expect(page.get_by_role("heading", name=SEARCH_EMPTY_TITLE)).to_be_visible()
    expect(page.get_by_role("heading", name=WINTERHAUS, exact=True)).to_be_visible()

    # The panel's door returns the whole shelf.
    page.get_by_role("button", name=SEARCH_EMPTY_CLEAR).click()
    expect(search).to_have_value("")
    expect(page.get_by_role("article")).to_have_count(3)
    assert_accessible(page)


def test_filter_facets_compose_within_and_across_groups(page: Page, installed: Stack) -> None:
    """Spec 3: the facets answer the loaded population's own genres and
    statuses with their counts; OR within a group, AND across the groups and
    the search; reset clears the popover's own controls."""
    klang = create_novel(
        KLANG, genre="Mystery & Noir, Literarische Belletristik", target_words=80000
    )
    patch_novel(str(klang["id"]), status="draft")
    gaertnerin = create_novel(GAERTNERIN, genre="Historischer Roman")
    patch_novel(str(gaertnerin["id"]), status="revision")
    create_novel(WINTERHAUS, genre="Mystery & Noir")
    tiefe = create_novel("Das Leuchten der Tiefe", genre="Literarische Belletristik")
    patch_novel(str(tiefe["id"]), status="final")
    create_novel("Nordlicht")  # created last → the hero; the grid holds four

    _goto_shelf(page)
    expect(page.get_by_role("article")).to_have_count(4)
    page.get_by_role("button", name="Filter", exact=True).click()
    dialog = page.get_by_role("dialog", name=FILTER_TITLE)
    expect(dialog).to_be_visible()

    # The genre facets: first appearance across the loaded rows, one count
    # per component — the hero included. The status facets: the vocabulary's
    # own order, only the values the rows carry.
    labels = dialog.locator("label")
    expect(labels.nth(0)).to_contain_text("Literarische Belletristik")
    expect(labels.nth(0).locator("span.tabular-nums")).to_have_text("2")
    expect(labels.nth(1)).to_contain_text("Mystery & Noir")
    expect(labels.nth(1).locator("span.tabular-nums")).to_have_text("2")
    expect(labels.nth(2)).to_contain_text("Historischer Roman")
    expect(labels.nth(2).locator("span.tabular-nums")).to_have_text("1")
    expect(labels.nth(3)).to_contain_text("Entwurf")
    expect(labels.nth(4)).to_contain_text("Überarbeitung")
    expect(labels.nth(5)).to_contain_text("Final")

    # OR within the genre group.
    dialog.locator("label").filter(has_text="Mystery & Noir").click()
    expect(dialog.get_by_role("checkbox", name="Mystery & Noir")).to_be_checked()
    expect(page.get_by_role("article")).to_have_count(2)
    expect(_card(page, KLANG)).to_be_visible()
    expect(_card(page, WINTERHAUS)).to_be_visible()
    expect(page.get_by_role("status")).to_have_text("2 Bücher gefunden")
    dialog.locator("label").filter(has_text="Literarische Belletristik").click()
    expect(page.get_by_role("article")).to_have_count(3)
    expect(_card(page, "Das Leuchten der Tiefe")).to_be_visible()
    dialog.locator("label").filter(has_text="Mystery & Noir").click()
    expect(page.get_by_role("article")).to_have_count(2)

    # AND across the groups: the status facet narrows the genre's answer.
    dialog.locator("label").filter(has_text="Final").click()
    expect(page.get_by_role("article")).to_have_count(1)
    expect(_card(page, "Das Leuchten der Tiefe")).to_be_visible()
    expect(page.get_by_role("status")).to_have_text("1 Buch gefunden")
    expect(dialog.get_by_text("2 ausgewählt", exact=True)).to_be_visible()

    # Reset clears the facets and the archive toggle — the whole grid returns.
    dialog.get_by_role("button", name="Zurücksetzen").click()
    expect(page.get_by_role("article")).to_have_count(4)
    expect(dialog.get_by_text("0 ausgewählt", exact=True)).to_be_visible()
    expect(dialog.get_by_role("checkbox", name="Final")).not_to_be_checked()

    # AND with the search: genre facet and title query together.
    dialog.locator("label").filter(has_text="Mystery & Noir").click()
    search = page.get_by_role("textbox", name=SEARCH_LABEL)
    search.fill("winter")
    expect(page.get_by_role("article")).to_have_count(1)
    expect(_card(page, WINTERHAUS)).to_be_visible()
    # The staged Escape: with text in the box it clears the query and stops —
    # the popover stays, the facet still narrows.
    search.press("Escape")
    expect(search).to_have_value("")
    expect(dialog).to_be_visible()
    expect(page.get_by_role("article")).to_have_count(2)
    assert_accessible(page)
    dialog.get_by_role("button", name="Filter schließen").click()
    expect(dialog).to_have_count(0)


def test_duplicate_grows_the_shelf_with_an_equal_copy(page: Page, installed: Stack) -> None:
    """Spec 4: Duplizieren copies the whole book — chapters, titles, positions
    and the scenes' prose — under „<Titel> (Kopie)"; the copy is the newest row
    and leads as the hero, the displaced hero joins the grid, and the copy
    starts fresh: unarchived, never exported, no volume."""
    novel = create_novel(KLANG, genre=KLANG_GENRE, blurb=KLANG_BLURB, target_words=80000)
    patch_novel(str(novel["id"]), status="draft")
    first = create_chapter(str(novel["id"]), "Das Flüstern im Wald")
    write_scene(str(first["id"]), word_body(300))
    second = create_chapter(str(novel["id"]), "Die Grenze zwischen Welten")
    write_scene(str(second["id"]), word_body(200))
    create_novel(WINTERHAUS)  # created last → the hero; Klang stands in the grid

    _goto_shelf(page)
    expect(page.get_by_role("article")).to_have_count(1)
    menu = _open_card_menu(page, KLANG)
    expect(menu.get_by_text(LAST_EXPORT, exact=True)).to_be_visible()
    expect(menu.get_by_text("—", exact=True)).to_be_visible()
    menu.get_by_role("button", name="Duplizieren").click()

    # The copy is the newest row: it leads as the hero, and the grid grows by
    # the displaced hero — three books on the shelf now.
    expect(page.get_by_role("heading", name=COPY_TITLE, exact=True)).to_be_visible()
    expect(page.get_by_role("article")).to_have_count(2)
    expect(_card(page, WINTERHAUS)).to_be_visible()
    expect(_card(page, KLANG)).to_be_visible()
    copy_hero = _hero(page)
    expect(copy_hero.get_by_text("500", exact=True)).to_be_visible()
    expect(copy_hero.get_by_text("/ 80.000 Wörter", exact=True)).to_be_visible()
    expect(copy_hero.get_by_text("2", exact=True)).to_be_visible()
    expect(copy_hero.get_by_text(KLANG_GENRE, exact=True)).to_be_visible()
    expect(copy_hero.get_by_text(KLANG_BLURB, exact=True)).to_be_visible()
    expect(copy_hero.get_by_text("Entwurf", exact=True)).to_be_visible()
    expect(_metric(page, "Aktive Projekte")).to_contain_text("3 Romane")
    expect(_metric(page, "Gesamtwörter")).to_contain_text("1.000")
    assert_accessible(page)

    # The honest check: content equality chapter by chapter, and the copy's
    # fresh shelf tracking beside the carried facts.
    original_id = _rows("SELECT id FROM novels WHERE title = :t", {"t": KLANG})[0][0]
    copy_id = _rows("SELECT id FROM novels WHERE title = :t", {"t": COPY_TITLE})[0][0]
    chapters_sql = "SELECT title, position FROM chapters WHERE novel_id = :n ORDER BY position"
    assert _rows(chapters_sql, {"n": copy_id}) == _rows(chapters_sql, {"n": original_id})
    # The prose rides the scenes (W4 §5): the copy carries each chapter's scenes
    # verbatim — title, body and position — in the same book reading order.
    scenes_sql = (
        "SELECT s.title, s.body, s.position FROM scenes s"
        " JOIN chapters c ON c.id = s.chapter_id"
        " WHERE c.novel_id = :n ORDER BY c.position, s.position"
    )
    assert _rows(scenes_sql, {"n": copy_id}) == _rows(scenes_sql, {"n": original_id})
    assert _rows(
        "SELECT genre, blurb, target_words, status, archived_at, last_exported_at, series_volume"
        " FROM novels WHERE title = :t",
        {"t": COPY_TITLE},
    ) == [(KLANG_GENRE, KLANG_BLURB, 80000, "draft", None, None, None)]


def test_export_lands_the_zip_and_stamps_the_menu(
    page: Page, installed: Stack, tmp_path: Path
) -> None:
    """Spec 5: Exportieren downloads the real artifact — the ZIP the
    interchange engine builds, named after the title's slug — and the receipt
    updates the menu's „Letzter Export" to the row's own stamp."""
    novel = _seed_klang_with_chapter(120)
    create_novel(WINTERHAUS)  # the hero; Klang stands in the grid with its menu

    _goto_shelf(page)
    menu = _open_card_menu(page, KLANG)
    expect(menu.get_by_text(LAST_EXPORT, exact=True)).to_be_visible()
    expect(menu.get_by_text("—", exact=True)).to_be_visible()

    with page.expect_download() as download_info:
        menu.get_by_role("button", name="Exportieren").click()
    download = download_info.value
    assert download.suggested_filename == "der-klang-des-eises.zip"

    # The artifact is the real archive: metadata, the chapter file, the body.
    artifact = tmp_path / "der-klang-des-eises.zip"
    download.save_as(artifact)
    with zipfile.ZipFile(artifact) as archive:
        names = archive.namelist()
        assert "metadata.json" in names
        assert "chapters/00-der-erste-schnee.md" in names
        metadata = json.loads(archive.read("metadata.json"))
        assert metadata["title"] == KLANG
        assert "Silbe0" in archive.read("chapters/00-der-erste-schnee.md").decode()

    # The menu stays open and the meta line reads the row's fresh stamp —
    # formatted by the browser's own de-DE rule, the app's formatDate grammar.
    expect(menu).to_be_visible()
    row = get_novel(str(novel["id"]))
    assert row["last_exported_at"] is not None
    expected_date = page.evaluate(
        "(iso) => new Intl.DateTimeFormat('de-DE',"
        " { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(iso))",
        row["last_exported_at"],
    )
    expect(menu.get_by_text(expected_date, exact=True)).to_be_visible()
    assert_accessible(page)

    # The honest check: the export trace is on the row, set by the export alone.
    assert _rows(
        "SELECT last_exported_at IS NOT NULL FROM novels WHERE title = :t", {"t": KLANG}
    ) == [(True,)]


def test_archive_confirm_leaves_and_wiederherstellen_returns(page: Page, installed: Stack) -> None:
    """Spec 6: Archivieren opens the drafted confirm (Abbrechen returns to the
    menu), the confirmed book leaves the grid, the archive-included list shows
    it with its marking and never as the hero, and Wiederherstellen returns it
    to the shelf — the restore advances the row's timestamp, so the returned
    book leads as the hero again. The symmetric round trip, on the rows too."""
    create_novel(KLANG, genre=KLANG_GENRE, target_words=80000)
    create_novel(WINTERHAUS)  # the hero; Klang stands in the grid

    _goto_shelf(page)
    expect(page.get_by_role("article")).to_have_count(1)

    # The confirm names the book; Abbrechen returns to the menu, nothing leaves.
    menu = _open_card_menu(page, KLANG)
    menu.get_by_role("button", name="Archivieren").click()
    confirm = page.get_by_role("dialog", name=CONFIRM_TITLE)
    expect(confirm).to_be_visible()
    expect(confirm).to_contain_text(
        f"«{KLANG}» verlässt das Regal und ruht im Archiv — jederzeit wiederherstellbar."
    )
    confirm.get_by_role("button", name="Abbrechen").click()
    expect(page.get_by_role("dialog", name=MENU_TITLE)).to_be_visible()
    expect(_card(page, KLANG)).to_be_visible()

    # Confirmed: the book leaves the grid, the hero stands, the row carries the stamp.
    page.get_by_role("dialog", name=MENU_TITLE).get_by_role("button", name="Archivieren").click()
    page.get_by_role("dialog", name=CONFIRM_TITLE).get_by_role(
        "button", name="Archivieren", exact=True
    ).click()
    expect(page.get_by_role("article")).to_have_count(0)
    expect(page.get_by_role("heading", name=WINTERHAUS, exact=True)).to_be_visible()
    expect(_metric(page, "Aktive Projekte")).to_contain_text("1 Roman")
    assert _rows("SELECT archived_at IS NOT NULL FROM novels WHERE title = :t", {"t": KLANG}) == [
        (True,)
    ]

    # The archive toggle is a real refetch: the book returns with its marking,
    # and the archived never leads — Winterhaus is still the hero.
    page.get_by_role("button", name="Filter", exact=True).click()
    switch = page.get_by_role("switch", name=ARCHIVE_SWITCH)
    expect(switch).to_have_attribute("aria-checked", "false")
    switch.click()
    expect(switch).to_have_attribute("aria-checked", "true")
    archived_card = _card(page, KLANG)
    expect(archived_card).to_be_visible()
    expect(archived_card.get_by_text(ARCHIVED_PILL, exact=True)).to_be_visible()
    expect(page.get_by_role("heading", name=WINTERHAUS, exact=True)).to_be_visible()
    assert_accessible(page)

    # The archived menu: its own header, its own meta line, the restore row.
    archived_menu = _open_card_menu(page, KLANG, archived=True)
    expect(archived_menu.get_by_text(ARCHIVED_AT, exact=True)).to_be_visible()
    archived_menu.get_by_role("button", name="Wiederherstellen").click()
    # The restore advances the row's updated_at: the returned book leads as
    # the hero again (the shelf's newest-first truth), the marking is gone
    # from the whole page, and Winterhaus falls back into the grid.
    expect(page.get_by_role("heading", name=KLANG, exact=True)).to_be_visible()
    expect(page.get_by_text(ARCHIVED_PILL, exact=True)).to_have_count(0)
    expect(_card(page, WINTERHAUS)).to_be_visible()
    assert _rows("SELECT archived_at IS NOT NULL FROM novels WHERE title = :t", {"t": KLANG}) == [
        (False,)
    ]

    # Toggle off: the restored book stays on the shelf — it is active again.
    # (The card menu's outside press closed the popover; reopen it.)
    page.get_by_role("button", name="Filter", exact=True).click()
    switch = page.get_by_role("switch", name=ARCHIVE_SWITCH)
    expect(switch).to_have_attribute("aria-checked", "true")
    switch.click()
    expect(switch).to_have_attribute("aria-checked", "false")
    expect(page.get_by_role("heading", name=KLANG, exact=True)).to_be_visible()
    expect(_card(page, WINTERHAUS)).to_be_visible()
    expect(_metric(page, "Aktive Projekte")).to_contain_text("2 Romane")


def test_the_hero_menu_archives_and_the_next_book_leads(page: Page, installed: Stack) -> None:
    """Spec 6b (#863): the hero wears the grid's own quick menu — the same
    28px trigger in its header row, the same three actions and meta line,
    never Wiederherstellen (the hero shows no archived book). Archiving the
    hero through the drafted confirm re-picks the next active book: the
    honest Nachrücken, no empty hero gap, and the row carries the stamp."""
    create_novel(GAERTNERIN, genre="Historischer Roman", target_words=50000)
    _seed_klang_with_chapter(1200)  # the chapter write makes Klang the hero

    _goto_shelf(page)
    hero = _hero(page)
    expect(page.get_by_role("heading", name=KLANG, exact=True)).to_be_visible()

    # The hero's own trigger opens the same menu: three actions, the honest
    # export dash, no restore variant.
    hero.get_by_role("button", name=CARD_OPTIONS).click()
    menu = page.get_by_role("dialog", name=MENU_TITLE)
    expect(menu).to_be_visible()
    for action in ("Duplizieren", "Exportieren", "Archivieren"):
        expect(menu.get_by_role("button", name=action)).to_be_visible()
    expect(menu.get_by_role("button", name="Wiederherstellen")).to_have_count(0)
    expect(menu.get_by_text(LAST_EXPORT, exact=True)).to_be_visible()
    expect(menu.get_by_text("—", exact=True)).to_be_visible()
    assert_accessible(page)

    # The drafted confirm names the hero; confirming archives it and the
    # next active book leads — Gärtnerin becomes the hero, no grid remains.
    menu.get_by_role("button", name="Archivieren").click()
    confirm = page.get_by_role("dialog", name=CONFIRM_TITLE)
    expect(confirm).to_be_visible()
    expect(confirm).to_contain_text(
        f"«{KLANG}» verlässt das Regal und ruht im Archiv — jederzeit wiederherstellbar."
    )
    confirm.get_by_role("button", name="Archivieren", exact=True).click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(page.get_by_role("heading", name=GAERTNERIN, exact=True)).to_be_visible()
    expect(_hero(page)).to_contain_text(GAERTNERIN)
    expect(page.get_by_role("heading", name=KLANG, exact=True)).to_have_count(0)
    expect(page.get_by_role("article")).to_have_count(0)
    expect(_metric(page, "Aktive Projekte")).to_contain_text("1 Roman")
    assert_accessible(page)

    # The honest check: the archive stamp is on the row, set by the menu alone.
    assert _rows("SELECT archived_at IS NOT NULL FROM novels WHERE title = :t", {"t": KLANG}) == [
        (True,)
    ]


def test_the_new_book_dialog_creates_the_hero_end_to_end(
    page: Page, installed_with_atelier: Stack
) -> None:
    """Spec 7: the atelier book stands on the shelf — the top bar's door opens
    the drafted modal (title required with the wizard's message, live cover,
    genre pills, the slider's bands) — and Anlegen posts once: the new book
    leads as the hero with a neutral word stand, its row carries the atelier's
    four answers (the inheritance note's truth) while the source row stands
    untouched, and a reopen finds the dialog's own answers forgotten."""
    _goto_shelf(page)
    # The setup book is the shelf's whole population: the hero, no grid.
    expect(
        page.get_by_role("heading", name=SETUP_ANSWERS["novel_title"], exact=True)
    ).to_be_visible()
    expect(page.get_by_role("article")).to_have_count(0)
    expect(_metric(page, "Aktive Projekte")).to_contain_text("1 Roman")

    # The top bar's door opens the modal over the scrimmed shelf.
    page.get_by_role("button", name=NEW_BOOK).click()
    dialog = page.get_by_role("dialog", name=DIALOG_TITLE)
    expect(dialog).to_be_visible()
    expect(dialog).to_have_attribute("aria-modal", "true")

    # No title, no create: the drafted message and the disabled CTA.
    title = dialog.get_by_label(TITLE_LABEL)
    expect(title).to_have_attribute("aria-invalid", "true")
    expect(dialog.get_by_text(TITLE_MISSING)).to_be_visible()
    expect(dialog.get_by_role("button", name=CREATE, exact=True)).to_be_disabled()

    # The title lifts the block and synchronizes onto the live cover.
    title.fill("Die Prüferin")
    expect(title).to_have_attribute("aria-invalid", "false")
    expect(dialog.get_by_text(TITLE_MISSING)).to_have_count(0)
    expect(dialog.get_by_text("Die Prüferin", exact=True)).to_be_visible()
    expect(dialog.get_by_role("button", name=CREATE, exact=True)).to_be_enabled()

    # Two genre pills, pressed; the slider's default band and Normseiten.
    dialog.get_by_role("button", name="Mystery & Noir", exact=True).click()
    dialog.get_by_role("button", name="Literarische Belletristik", exact=True).click()
    expect(dialog.get_by_role("button", name="Mystery & Noir", exact=True)).to_have_attribute(
        "aria-pressed", "true"
    )
    slider = dialog.get_by_label(WORDS_LABEL)
    expect(slider).to_have_value("65000")
    expect(dialog.get_by_text("65.000", exact=True)).to_be_visible()
    expect(dialog.get_by_text("Standard-Roman", exact=True)).to_be_visible()
    expect(dialog.get_by_text("(60–80k W.)", exact=True)).to_be_visible()
    expect(dialog.get_by_text("Entspricht ca. 240 Normseiten im Buchdruckformat.")).to_be_visible()
    expect(dialog.get_by_text(INHERITANCE_NOTE)).to_be_visible()
    assert_accessible(page)

    # The keyboard path down the slider: Home to the floor, two steps up.
    slider.press("Home")
    slider.press("ArrowRight")
    slider.press("ArrowRight")
    expect(slider).to_have_value("30000")
    expect(dialog.get_by_text("30.000", exact=True)).to_be_visible()
    expect(dialog.get_by_text("Novelle", exact=True)).to_be_visible()
    expect(dialog.get_by_text("(20–40k W.)", exact=True)).to_be_visible()
    expect(dialog.get_by_text("Entspricht ca. 111 Normseiten im Buchdruckformat.")).to_be_visible()

    # One POST: the dialog closes, the shelf's own refetch carries the book —
    # the newest row leads as the hero, the atelier book joins the grid, the
    # word stand honestly neutral.
    dialog.get_by_role("button", name=CREATE, exact=True).click()
    expect(dialog).to_have_count(0)
    expect(page.get_by_role("heading", name="Die Prüferin", exact=True)).to_be_visible()
    expect(page.get_by_role("article")).to_have_count(1)
    expect(_card(page, SETUP_ANSWERS["novel_title"])).to_be_visible()
    hero = _hero(page)
    # Word stand and chapter count both honestly zero — two zero spans.
    expect(hero.get_by_text("0", exact=True)).to_have_count(2)
    expect(hero.get_by_text("Kapitel", exact=True)).to_be_visible()
    expect(hero.get_by_text("/ 30.000 Wörter", exact=True)).to_be_visible()
    expect(hero.get_by_text("0 %", exact=True)).to_be_visible()
    # The banner's goal is the atelier's — none is stored on this fresh
    # instance, so the honest unset stands (row 25), not the new book's pin.
    expect(_banner(page)).to_contain_text("Noch kein Schreibziel")
    expect(_metric(page, "Aktive Projekte")).to_contain_text("2 Romane")
    expect(_metric(page, "Gesamtwörter")).to_contain_text("0")
    expect(_metric(page, "Schreibstreak")).to_contain_text("0 Tage")
    # Focus returns to the opener — the top bar's door, which survives.
    expect(page.get_by_role("button", name=NEW_BOOK)).to_be_focused()
    assert_accessible(page)

    # The honest check: the new row carries its three answers AND the
    # atelier's four — the inheritance note's truth, flowed through the real
    # setup — while the source row stands exactly as setup left it.
    assert _rows(
        "SELECT title, genre, target_words, author_typology, dramatic_form, ai_role,"
        " canon_strictness FROM novels ORDER BY created_at"
    ) == [
        (
            SETUP_ANSWERS["novel_title"],
            SETUP_ANSWERS["genre"],
            SETUP_ANSWERS["target_words"],
            SETUP_ANSWERS["author_typology"],
            SETUP_ANSWERS["dramatic_form"],
            SETUP_ANSWERS["ai_role"],
            SETUP_ANSWERS["canon_strictness"],
        ),
        (
            "Die Prüferin",
            "Mystery & Noir, Literarische Belletristik",
            30000,
            SETUP_ANSWERS["author_typology"],
            SETUP_ANSWERS["dramatic_form"],
            SETUP_ANSWERS["ai_role"],
            SETUP_ANSWERS["canon_strictness"],
        ),
    ]
    assert _rows("SELECT id FROM chapters") == []

    # A reopen finds the answers forgotten — transient by construction.
    page.get_by_role("button", name=NEW_BOOK).click()
    reopened = page.get_by_role("dialog", name=DIALOG_TITLE)
    expect(reopened.get_by_label(TITLE_LABEL)).to_have_value("")
    expect(reopened.get_by_label(TITLE_LABEL)).to_have_attribute("aria-invalid", "true")
    reopened.get_by_role("button", name="Abbrechen").click()
    expect(reopened).to_have_count(0)


def test_the_empty_shelf_door_creates_with_no_source_to_inherit(
    page: Page, installed: Stack
) -> None:
    """Spec 7b: the empty shelf's own door — the setup book is gone, so no
    source row remains: the dialog creates the hero with the three answers
    and honest NULLs in the atelier's four columns (no answer propagates,
    nothing is guessed), the panel retires with the create, and focus lands
    on the surviving top-bar door."""
    _goto_shelf(page)
    expect(page.get_by_role("heading", name=EMPTY_TITLE)).to_be_visible()
    expect(_metric(page, "Aktive Projekte")).to_contain_text("0 Romane")
    expect(_metric(page, "Schreibstreak")).to_contain_text("0 Tage")

    # The empty panel's own door opens the modal over the scrimmed shelf.
    empty_panel = page.locator("section").filter(has=page.get_by_text(EMPTY_TITLE, exact=True))
    empty_panel.get_by_role("button", name=NEW_BOOK).click()
    dialog = page.get_by_role("dialog", name=DIALOG_TITLE)
    expect(dialog).to_be_visible()
    expect(dialog).to_have_attribute("aria-modal", "true")
    expect(dialog.get_by_text(INHERITANCE_NOTE)).to_be_visible()

    dialog.get_by_label(TITLE_LABEL).fill("Die Prüferin")
    dialog.get_by_role("button", name=CREATE, exact=True).click()
    expect(dialog).to_have_count(0)
    expect(page.get_by_role("heading", name="Die Prüferin", exact=True)).to_be_visible()
    expect(page.get_by_role("article")).to_have_count(0)
    expect(_metric(page, "Aktive Projekte")).to_contain_text("1 Roman")
    # The create retired the empty panel's door: focus lands on the top bar's.
    expect(page.get_by_role("button", name=NEW_BOOK)).to_be_focused()
    assert_accessible(page)

    # The honest check: the three answers on the row, and no wizard setting —
    # the source book was deleted, so there is nothing to inherit.
    assert _rows(
        "SELECT title, genre, target_words, author_typology, dramatic_form, ai_role,"
        " canon_strictness FROM novels"
    ) == [("Die Prüferin", None, 65000, None, None, None, None)]
    assert _rows("SELECT id FROM chapters") == []


def test_an_api_chapter_write_moves_the_banner_through_the_seam(
    page: Page, installed: Stack
) -> None:
    """Spec 8: the invalidation seam, proven in the browser. A chapter written
    through the API feeds the ledger; the banner holds its cached answer until
    a real shelf write fires the family — then today's words, the streak and
    the average move WITHOUT a reload, and the aggregate is the rows' own."""
    create_novel(WINTERHAUS, target_words=40000)
    novel = create_novel(KLANG, target_words=60000)  # created last → the hero
    # The daily goal rides the same aggregate (row 25): 600 stored, the
    # day empty — the remainder moves with the day's words, not the book.
    set_daily_goal(600)

    _goto_shelf(page)
    banner = _banner(page)
    expect(banner).to_contain_text(BANNER_NEUTRAL)
    expect(banner).to_contain_text("Heutiges Schreibziel: 600 Wörter")
    expect(_metric(page, "Schreibstreak")).to_contain_text("0 Tage")
    expect(banner.get_by_text("0,0 W/Tag", exact=True)).to_be_visible()

    # The API write: 150 words land on today's ledger row.
    chapter = create_chapter(str(novel["id"]), "Der erste Schnee")
    write_scene(str(chapter["id"]), word_body(150))

    # The cache holds — no invalidation has fired, the banner still speaks the
    # old answer (the 30 s staleTime, honestly stale until the family asks).
    expect(banner).to_contain_text(BANNER_NEUTRAL)
    expect(_metric(page, "Schreibstreak")).to_contain_text("0 Tage")

    # A real shelf write through the family: archive the grid book via the
    # drafted confirm. The one seam invalidates novels AND activity.
    _archive_through_confirm(page, WINTERHAUS)
    expect(page.get_by_role("article")).to_have_count(0)

    # The banner moved without a reload: the day's words, the streak, the
    # average and the daily goal's remainder — all the aggregate's own.
    expect(banner).to_contain_text("Du hast heute bereits 150 Wörter verfasst.")
    expect(banner).to_contain_text("Noch 450 Wörter bis zum Tagesziel.")
    expect(banner).to_contain_text("Heutiges Schreibziel: 600 Wörter")
    expect(_metric(page, "Schreibstreak")).to_contain_text("1 Tag")
    expect(banner.get_by_text("5,0 W/Tag", exact=True)).to_be_visible()
    assert_accessible(page)

    # The honest check: the aggregate and the ledger agree with the screen.
    aggregate = get_activity()
    assert aggregate["today_words"] == 150
    assert aggregate["streak_days"] == 1
    assert aggregate["weekly_average"] == 5.0
    assert aggregate["points"][-1]["words"] == 150
    assert aggregate["daily_goal_words"] == 600
    assert aggregate["goal_met"] is False
    assert aggregate["goal_remaining"] == 450
    assert _rows("SELECT SUM(words) FROM daily_words") == [(150,)]


def test_the_banners_daily_goal_speaks_unset_open_and_met(page: Page, installed: Stack) -> None:
    """Spec 8b (W4 row 25): the banner's goal line is the atelier's daily
    goal — the settings PATCH stores it, the aggregate carries the day's
    progress, and the three faces speak honestly: no goal stored is the
    neutral, an open goal owes the remainder, a reached day speaks the
    done-state copy. The hero book's target never stands in for it."""
    novel = create_novel(KLANG, target_words=80000)
    chapter = create_chapter(str(novel["id"]), "Der erste Schnee")
    write_scene(str(chapter["id"]), word_body(1200))

    _goto_shelf(page)
    banner = _banner(page)
    # Unset: the honest neutral — the book's 80.000-word target is the
    # book's truth (the hero panel carries it), never the banner's goal.
    expect(banner).to_contain_text("Noch kein Schreibziel")
    expect(banner).to_contain_text("Du hast heute bereits 1.200 Wörter verfasst.")
    expect(banner).not_to_contain_text("Ziel für")
    expect(banner).not_to_contain_text("Tagesziel")
    aggregate = get_activity()
    assert aggregate["daily_goal_words"] is None
    assert aggregate["goal_met"] is False
    assert aggregate["goal_remaining"] == 0

    # Open: 2.000 stored, 1.200 written — 800 remain. The goal change is
    # the settings' own write; a reload asks the aggregate again.
    set_daily_goal(2000)
    page.reload()
    expect(page.get_by_role("heading", name=SHELF_TITLE)).to_be_visible()
    banner = _banner(page)
    expect(banner).to_contain_text("Heutiges Schreibziel: 2.000 Wörter")
    expect(banner).to_contain_text("Noch 800 Wörter bis zum Tagesziel.")
    aggregate = get_activity()
    assert aggregate["daily_goal_words"] == 2000
    assert aggregate["goal_met"] is False
    assert aggregate["goal_remaining"] == 800

    # Met: the goal lowered to what the day already holds — the done-state
    # copy stands, no remainder beside it.
    set_daily_goal(1000)
    page.reload()
    expect(page.get_by_role("heading", name=SHELF_TITLE)).to_be_visible()
    banner = _banner(page)
    expect(banner).to_contain_text("Heutiges Schreibziel: 1.000 Wörter")
    expect(banner).to_contain_text("Tagesziel erreicht.")
    expect(banner).not_to_contain_text("bis zum Tagesziel")
    aggregate = get_activity()
    assert aggregate["daily_goal_words"] == 1000
    assert aggregate["goal_met"] is True
    assert aggregate["goal_remaining"] == 0
    assert_accessible(page)

    # The honest check: the goal is the user's row, the words the ledger's.
    assert _rows("SELECT daily_goal_words FROM users") == [(1000,)]
    assert _rows("SELECT SUM(words) FROM daily_words") == [(1200,)]


def test_pre_setup_root_hands_off_to_the_welcome(page: Page, uninstalled: Stack) -> None:
    """Spec 9: the suite instance's uninstalled face — `/` redirects to the
    welcome at `/setup`, the wizard's door stands, and no user row exists."""
    page.goto(BASE + "/")
    expect(page).to_have_url(BASE + "/setup")
    expect(page.get_by_role("heading", name=WELCOME_HEADING)).to_be_visible()
    expect(page).to_have_title("Willkommen im Atelier — Narrare")
    expect(page.get_by_role("link", name="Atelier einrichten")).to_have_attribute(
        "href", "/setup/basis"
    )
    assert _rows("SELECT id FROM users") == []
    assert_accessible(page)


def test_post_setup_setup_hands_back_to_the_shelf(page: Page, installed: Stack) -> None:
    """Spec 10: the inverse gate — an installed instance has no wizard;
    `/setup` and a step deep link both redirect back to the shelf."""
    page.goto(BASE + "/setup")
    expect(page).to_have_url(BASE + "/")
    expect(page.get_by_role("heading", name=SHELF_TITLE)).to_be_visible()
    page.goto(BASE + "/setup/basis")
    expect(page).to_have_url(BASE + "/")
    expect(page.get_by_role("heading", name=SHELF_TITLE)).to_be_visible()


def test_the_chrome_frames_the_shelf(page: Page, installed: Stack) -> None:
    """W4 Task 10 (D15, D17): the app-wide rail and topbar frame the shelf —
    the nav's live doors (shelf, editor, Wissen live with the knowledge
    wave W5), the two honest later-wave ones, the book switcher's real
    novels menu, the interim sync state, the real word total, the disabled
    ⌘K chip (#882), the language chip as the real switcher, the tri-state
    theme toggle and the user block's fallback.
    The database assertions remain the honest check."""
    create_novel(WINTERHAUS)
    novel = create_novel(KLANG, genre=KLANG_GENRE, target_words=80000)
    chapter = create_chapter(str(novel["id"]), "Der erste Schnee")
    write_scene(str(chapter["id"]), word_body(1200))

    _goto_shelf(page)
    topbar = page.locator("header")
    # The rail's nav is one landmark; the switcher, sync, theme and user
    # block stand in the aside around it (complementary).
    aside = page.get_by_role("complementary")

    # The rail: the shelf door live and current, the editor door live with
    # the workspace (W4 Task 11 — it opens the active book), the Wissen
    # door live with the knowledge wave (W5 — the active book's lore
    # graph), the two later-wave doors honestly disabled.
    rail = page.get_by_role("navigation", name="Navigation")
    expect(rail.get_by_role("link", name="Bücherregal")).to_have_attribute("aria-current", "page")
    editor = rail.get_by_role("link", name="Editor")
    expect(editor).to_have_attribute("href", f"/novels/{novel['id']}")
    expect(editor).not_to_have_attribute("aria-current", "page")
    wissen = rail.get_by_role("link", name="Wissen")
    expect(wissen).to_have_attribute("href", f"/novels/{novel['id']}/knowledge/graph")
    expect(wissen).not_to_have_attribute("aria-current", "page")
    for label in ("Planung", "Einstellungen"):
        expect(rail.get_by_role("button", name=label)).to_be_disabled()

    # The topbar's shelf face (tile 7): the breadcrumb, the real total over
    # the active population, the interim save chip the rail foot shares.
    expect(topbar.get_by_role("link", name="Atelier")).to_have_attribute("href", "/")
    expect(topbar.get_by_text("Das Bücherregal")).to_be_visible()
    expect(topbar.get_by_text("1.200 W. Gesamt")).to_be_visible()
    expect(topbar.get_by_text("Gespeichert")).to_be_visible()
    # The rail's own label stands when the rail glides open on hover — the
    # collapsed face is the dot alone (the draft's two faces).
    rail.hover()
    expect(aside.get_by_text("Gespeichert")).to_be_visible()

    # The ⌘K chip: honestly disabled until the shell palette wave (#882).
    expect(topbar.get_by_role("button", name="Suchen")).to_be_disabled()

    # The book switcher: the user's real novels, the active one marked, and
    # the workspace navigation (W4 Task 11 — each row opens its book).
    aside.get_by_role("button", name=re.compile("Aktives Buch")).click()
    menu = page.get_by_role("menu", name="Atelier-Werke")
    expect(menu).to_be_visible()
    expect(menu.get_by_text("2 Romane")).to_be_visible()
    active_row = menu.get_by_role("menuitem", name=re.compile(KLANG))
    expect(active_row).to_have_attribute("aria-current", "true")
    expect(active_row).to_contain_text("1 %")  # 1.200 / 80.000, the row's own
    expect(menu.get_by_role("menuitem", name="Neues Buch anlegen")).to_be_visible()
    # The rows open their book's workspace; the menu closes on the choice.
    # Winterhaus holds no chapters — the empty-book face answers honestly.
    winter_row = menu.get_by_role("menuitem", name=re.compile(WINTERHAUS))
    winter_id = str(_rows("SELECT id FROM novels WHERE title = :t", {"t": WINTERHAUS})[0][0])
    winter_row.click()
    expect(menu).to_have_count(0)
    expect(page).to_have_url(f"{BASE}/novels/{winter_id}")
    expect(page.get_by_role("heading", name="Ein unbeschriebenes Werk")).to_be_visible()
    # Back to the shelf for the chrome's remaining faces.
    page.goto(BASE + "/")
    expect(page.get_by_role("heading", name=SHELF_TITLE)).to_be_visible()

    # The language chip is the real switcher (D17): the choice PATCHes the
    # row, the whole chrome and shelf speak it, and the row is the record.
    topbar.get_by_role("button", name=re.compile("Sprache")).click()
    page.get_by_role("menu", name="Sprache").get_by_role(
        "menuitemradio", name=re.compile("English")
    ).click()
    expect(page.get_by_role("heading", name="The Bookshelf")).to_be_visible()
    expect(rail.get_by_role("link", name="Bookshelf")).to_be_visible()
    assert _rows("SELECT locale FROM users") == [("en",)]
    # And back through the same chip — one contract, every face.
    topbar.get_by_role("button", name=re.compile("Language")).click()
    page.get_by_role("menu", name="Language").get_by_role(
        "menuitemradio", name=re.compile("Deutsch")
    ).click()
    expect(page.get_by_role("heading", name=SHELF_TITLE)).to_be_visible()
    assert _rows("SELECT locale FROM users") == [("de",)]

    # The theme toggle: the first step leaves the system for light, applied
    # at once and stored on the row — the document and the row agree.
    aside.get_by_role("button", name=re.compile("Erscheinungsbild")).click()
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
    assert _rows("SELECT theme FROM users") == [("light",)]

    # The user block: the local row carries neither name nor email — the
    # honest profile neutral, no tier; a stored author name answers with
    # its initials after the boot re-reads the row. The name line stands
    # in the open rail (the collapsed face is the avatar chip alone).
    expect(aside.get_by_title("Benutzerprofil")).to_be_visible()
    set_author_name("H. Calder")
    page.reload()
    expect(page.get_by_role("heading", name=SHELF_TITLE)).to_be_visible()
    rail.hover()
    expect(aside.get_by_text("H. Calder")).to_be_visible()
    expect(aside.get_by_text("HC")).to_be_visible()
    expect(aside.get_by_title("Benutzerprofil: H. Calder")).to_be_visible()

    assert_accessible(page)


def test_the_dark_shelf_face_clears_the_axe_floor(page: Page, installed: Stack) -> None:
    """Spec 11: the settings row's dark theme, adopted at boot — the shelf
    renders on the tokens' dark halves (the body's own dark ground), and the
    populated face plus the open quick menu clear the axe WCAG A/AA floor."""
    set_theme("dark")
    create_novel(WINTERHAUS)
    _seed_klang_with_chapter(1200)  # the hero; Winterhaus stands in the grid

    _goto_shelf(page)
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(22, 20, 15)"
    expect(page.get_by_role("heading", name=KLANG, exact=True)).to_be_visible()
    expect(_card(page, WINTERHAUS)).to_be_visible()
    # No goal stored on this instance — the banner's honest unset (row 25).
    expect(_banner(page)).to_contain_text("Noch kein Schreibziel")
    assert_accessible(page)

    # The quick menu's dark face — the popover over the dark card.
    menu = _open_card_menu(page, WINTERHAUS)
    expect(menu.get_by_text(LAST_EXPORT, exact=True)).to_be_visible()
    assert_accessible(page)
    page.locator("h1").click()  # an outside press closes the grid menu

    # The hero menu's dark face (#863) — the same popover over the hero.
    _hero(page).get_by_role("button", name=CARD_OPTIONS).click()
    hero_menu = page.get_by_role("dialog", name=MENU_TITLE)
    expect(hero_menu.get_by_text(LAST_EXPORT, exact=True)).to_be_visible()
    assert_accessible(page)
    page.locator("h1").click()  # an outside press closes the hero menu

    # The chrome's dark face (W4 Task 10) — the same rail and topbar on the
    # tokens' dark halves, the theme toggle naming the stored choice, and
    # the language chip's open menu clearing the floor too.
    rail = page.get_by_role("navigation", name="Navigation")
    expect(rail.get_by_role("link", name="Bücherregal")).to_have_attribute("aria-current", "page")
    expect(page.locator("header").get_by_text("1.200 W. Gesamt")).to_be_visible()
    expect(
        page.get_by_role("complementary").get_by_role(
            "button", name=re.compile("Erscheinungsbild: Dunkel")
        )
    ).to_be_visible()
    page.locator("header").get_by_role("button", name=re.compile("Sprache")).click()
    expect(page.get_by_role("menu", name="Sprache")).to_be_visible()
    assert_accessible(page)
