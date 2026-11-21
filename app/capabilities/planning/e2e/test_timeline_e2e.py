# The German face's own quotes and dashes are the catalog text these tests
# assert literally — intentional characters, not confusable typos.
"""The chronology on the real stack (W6 Task 6): the planning capability's
first surface, proven over browser, API and Postgres.

The round-trip walks the product's own doors — create with date label,
chapter link, names and position, the edit, the delete through its confirm —
and reads the server's truth back through the planning API after every leg,
so the list the browser shows and the rows Postgres keeps are proven to be
one truth. The filters compose (AND across kinds, OR within names) over the
name chips the events themselves populate, the scene-status counters derive
from the real fan-out, and the honest faces (empty, no results) keep the
subbar with its sibling doors standing — W5 #923's rule, now on planning.
The rail's Planung door opens the active book's chronology and wears the
active face on the planning routes.
"""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.capabilities.planning.e2e.conftest import (
    create_chapter,
    create_event,
    create_novel,
    goto_timeline,
    list_events,
    save_scenes,
    scene,
    set_theme,
)
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.stack import WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = WEB_URL


def _open(page: Page, novel_id: str) -> None:
    goto_timeline(page, novel_id)


def _create_event(
    page: Page,
    *,
    title: str,
    date_label: str = "",
    description: str = "",
    chapter: str | None = None,
    names: list[str] | None = None,
    position: str | None = None,
) -> None:
    """The create dialog's fields, one lead at a time. ``chapter`` names the
    option's visible label („Kapitel 1: …"), the names commit on Enter."""
    page.get_by_role("button", name="Neues Ereignis anlegen").click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible()
    dialog.get_by_label("Titel des Ereignisses").fill(title)
    if date_label:
        dialog.get_by_label("Freies Datumslabel").fill(date_label)
    if description:
        dialog.get_by_label("Beschreibung / Notiz").fill(description)
    if chapter is not None:
        dialog.get_by_label("Kapitel-Zuordnung (optional)").select_option(label=chapter)
    for name in names or []:
        dialog.get_by_label("Beteiligte Figuren (Klartext)").fill(name)
        dialog.get_by_label("Beteiligte Figuren (Klartext)").press("Enter")
    if position is not None:
        dialog.get_by_label("Position in der Chronologie").fill(position)
    dialog.get_by_role("button", name="Speichern").click()
    expect(page.get_by_role("dialog")).to_have_count(0)


def test_the_chronology_round_trip(page: Page, installed: Stack) -> None:
    """Create with date, link and names → the card's real fields → the edit
    → the server's row → the delete through its confirm → the honest list.
    The API is asked back after every leg: the browser and Postgres agree."""
    novel = create_novel("Das Signal", target_words=65000)
    novel_id = str(novel["id"])
    chapter = create_chapter(novel_id, "Ankunft")
    chapter_id = str(chapter["id"])
    _open(page, novel_id)
    expect(page.get_by_test_id("timeline-empty")).to_be_visible()

    _create_event(
        page,
        title="Der Große Bruch",
        date_label="2278",
        description="Nevada-Tiefraumarray verliert 41 % der Verbindung.",
        chapter="Kapitel 1: Ankunft",
        names=["Maya Chen", "Lin Chen"],
        position="2",
    )
    card = page.get_by_test_id("timeline-card").filter(has_text="Der Große Bruch")
    expect(card).to_be_visible()
    expect(card).to_contain_text("2278")
    expect(card).to_contain_text("Nevada-Tiefraumarray verliert 41 % der Verbindung.")
    expect(card).to_contain_text("Maya Chen")
    expect(card).to_contain_text("Lin Chen")
    expect(card).to_contain_text("Kapitel 1")
    expect(page.get_by_test_id("timeline-ordered")).to_contain_text("1 eingeordnetes Ereignis")

    # The server's own row — the browser wrote what the API keeps.
    events = list_events(novel_id)
    assert len(events) == 1
    assert events[0]["title"] == "Der Große Bruch"
    assert events[0]["date_label"] == "2278"
    assert events[0]["chapter_id"] == chapter_id
    assert events[0]["character_names"] == ["Maya Chen", "Lin Chen"]
    assert events[0]["position"] == 2

    # The edit: the card opens the form, the date moves, the chapter link
    # clears — the PUT only carries what changed.
    card.get_by_text("Der Große Bruch").click()
    edit = page.get_by_role("dialog")
    expect(edit).to_be_visible()
    expect(edit.get_by_text("Ereignis bearbeiten")).to_be_visible()
    edit.get_by_label("Freies Datumslabel").fill("Winter 2279")
    edit.get_by_label("Kapitel-Zuordnung (optional)").select_option(
        label="Keinem Kapitel zugeordnet"
    )
    edit.get_by_role("button", name="Änderungen speichern").click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(card).to_contain_text("Winter 2279")
    expect(card).to_contain_text("Kein Kapitel")
    edited = list_events(novel_id)
    assert edited[0]["date_label"] == "Winter 2279"
    assert edited[0]["chapter_id"] is None

    # The delete: the edit's foot hands off to the confirm, which names
    # the loss; the list then answers honestly — nothing left.
    card.get_by_text("Der Große Bruch").click()
    edit = page.get_by_role("dialog")
    edit.get_by_role("button", name="Ereignis unwiderruflich aus der Chronologie entfernen").click()
    confirm = page.get_by_role("alertdialog")
    expect(confirm).to_contain_text("„Der Große Bruch“ verschwindet aus der Chronologie.")
    confirm.get_by_role("button", name="Löschen").click()
    expect(page.get_by_role("alertdialog")).to_have_count(0)
    expect(page.get_by_test_id("timeline-empty")).to_be_visible()
    assert list_events(novel_id) == []
    assert_accessible(page)


def test_the_unordered_row_stands_last(page: Page, installed: Stack) -> None:
    """The undated placeholder opens the same create door; the row it mints
    stands in the dashed unordered section, its chapter chip carrying the
    draft's „Geplant" prefix — the plan is real, the order is not."""
    novel = create_novel("Das Winterhaus")
    novel_id = str(novel["id"])
    chapter = create_chapter(novel_id, "Ankunft")
    # The board with its sections stands only once an event exists — the
    # empty face owns the zero state. One positioned row seeds the board.
    create_event(
        novel_id,
        title="Der Große Bruch",
        date_label="2278",
        chapter_id=str(chapter["id"]),
        position=1,
    )
    _open(page, novel_id)

    page.get_by_role("button", name="Neues undatiertes Ereignis anlegen").click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_text("Ereignis anlegen")).to_be_visible()
    dialog.get_by_label("Titel des Ereignisses").fill("Öffnung von Sektor D-4")
    dialog.get_by_label("Kapitel-Zuordnung (optional)").select_option(label="Kapitel 1: Ankunft")
    dialog.get_by_label("Beteiligte Figuren (Klartext)").fill("Maya Chen")
    dialog.get_by_label("Beteiligte Figuren (Klartext)").press("Enter")
    dialog.get_by_role("button", name="Speichern").click()
    expect(page.get_by_role("dialog")).to_have_count(0)

    unordered = page.get_by_test_id("timeline-unordered")
    card = unordered.get_by_test_id("timeline-card").filter(has_text="Öffnung von Sektor D-4")
    expect(card).to_be_visible()
    expect(card).to_contain_text("Kein Datum")
    expect(card).to_contain_text("Geplant Kapitel 1")
    expect(card).to_contain_text("Maya Chen")
    # The seeded row stands in the ordered section above the draft register.
    ordered = page.get_by_test_id("timeline-ordered")
    expect(
        ordered.get_by_test_id("timeline-card").filter(has_text="Der Große Bruch")
    ).to_be_visible()
    expect(ordered).to_contain_text("1 eingeordnetes Ereignis")
    # The name chips populate from the events themselves.
    expect(
        page.get_by_test_id("timeline-name-filters").get_by_role("button", name="Maya Chen")
    ).to_be_visible()


def test_the_filters_narrow_and_clear_honestly(page: Page, installed: Stack) -> None:
    """The name chips and the quick filters compose (AND across, OR within),
    the counters derive from the real scene fan-out, and the empty
    intersection answers with its own face and its clear door."""
    novel = create_novel("Der Nebel")
    novel_id = str(novel["id"])
    chapter = create_chapter(novel_id, "Ankunft")
    chapter_id = str(chapter["id"])
    other = create_chapter(novel_id, "Notfall-Code")
    other_id = str(other["id"])
    # The fan-out's real answer: one complete scene, one planned — the
    # counters count the lifecycle, not a guess.
    save_scenes(novel_id, chapter_id, [scene("Kalibrierung", status="complete")])
    save_scenes(novel_id, other_id, [scene("Der Ausfall", status="planned")])
    create_event(
        novel_id,
        title="Unglück auf Station 7",
        date_label="14. Nov 2284",
        character_names=["Maya Chen", "Lin Chen"],
        chapter_id=chapter_id,
        position=1,
    )
    create_event(
        novel_id,
        title="Der Große Bruch",
        date_label="2278",
        character_names=["Lin Chen"],
        position=2,
    )
    create_event(novel_id, title="Öffnung von Sektor D-4", character_names=["Maya Chen"])
    _open(page, novel_id)

    cards = page.get_by_test_id("timeline-card")
    expect(cards).to_have_count(3)
    counters = page.get_by_test_id("timeline-counters")
    expect(counters).to_contain_text("1 verfasste Szene")
    expect(counters).to_contain_text("1 geplante Szene")
    expect(counters).to_contain_text("1 Ereignis ohne Datum")

    # A name narrows to its events; the second name widens (OR within).
    page.get_by_test_id("timeline-name-filters").get_by_role("button", name="Maya Chen").click()
    expect(cards).to_have_count(2)
    page.get_by_test_id("timeline-name-filters").get_by_role("button", name="Lin Chen").click()
    expect(cards).to_have_count(3)

    # „Ohne Datum" composes with the names (AND across): Maya carries the
    # undated fragment, so the pair's intersection keeps it — one card.
    page.get_by_role("button", name="Ohne Datum").click()
    expect(cards).to_have_count(1)
    expect(cards.filter(has_text="Öffnung von Sektor D-4")).to_be_visible()

    # Lin alone stands only on dated rows: the intersection is empty — the
    # honest no-results face stands, and its clear door resets both kinds.
    page.get_by_test_id("timeline-name-filters").get_by_role("button", name="Maya Chen").click()
    expect(page.get_by_test_id("timeline-no-results")).to_be_visible()
    page.get_by_role("button", name="Filter zurücksetzen").click()
    expect(cards).to_have_count(3)

    # The quick filters alone: „Mit Kapitel" keeps the linked row alone.
    page.get_by_role("button", name="Mit Kapitel").click()
    expect(cards).to_have_count(1)
    expect(cards.filter(has_text="Unglück auf Station 7")).to_be_visible()
    assert_accessible(page)


def test_the_empty_chronology_keeps_the_sibling_doors(page: Page, installed: Stack) -> None:
    """The empty face never stands alone: the subbar's sibling doors walk
    to the storyboard and the causality strip and back, each answering with
    its own honest face — and the rail's Planung door opens the active
    book's chronology, wearing the active face on the planning routes."""
    novel = create_novel("Das leere Buch")
    novel_id = str(novel["id"])
    _open(page, novel_id)
    expect(page.get_by_test_id("timeline-empty")).to_be_visible()

    page.get_by_test_id("timeline-storyboard-door").click()
    expect(page.get_by_test_id("storyboard-page")).to_be_visible()
    expect(page.get_by_test_id("storyboard-empty")).to_be_visible()
    page.get_by_test_id("storyboard-causality-door").click()
    expect(page.get_by_test_id("causality-page")).to_be_visible()
    expect(page.get_by_test_id("causality-empty")).to_be_visible()
    page.get_by_test_id("causality-timeline-door").click()
    expect(page.get_by_test_id("timeline-page")).to_be_visible()
    expect(page.get_by_test_id("timeline-empty")).to_be_visible()

    # The rail's Planung door: live with a book standing, the active face
    # on the planning route it stands on.
    rail = page.locator("aside").filter(has=page.get_by_role("navigation", name="Navigation"))
    planung = rail.get_by_role("link", name="Planung")
    expect(planung).to_have_attribute("href", f"/novels/{novel_id}/planning/timeline")
    expect(planung).to_have_attribute("aria-current", "page")
    planung.click()
    expect(page.get_by_test_id("timeline-page")).to_be_visible()


def test_the_dark_chronology_clears_the_axe_floor(page: Page, installed: Stack) -> None:
    """The board and the open create dialog on the tokens' dark halves —
    the same WCAG A/AA floor the light face clears."""
    set_theme("dark")
    novel = create_novel("Das dunkle Buch")
    novel_id = str(novel["id"])
    chapter = create_chapter(novel_id, "Ankunft")
    create_event(
        novel_id,
        title="Der Große Bruch",
        date_label="2278",
        chapter_id=str(chapter["id"]),
        position=1,
    )
    _open(page, novel_id)
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    page.get_by_test_id("timeline-card").filter(has_text="Der Große Bruch").get_by_text(
        "Der Große Bruch"
    ).click()
    expect(page.get_by_role("dialog")).to_be_visible()
    assert_accessible(page)
