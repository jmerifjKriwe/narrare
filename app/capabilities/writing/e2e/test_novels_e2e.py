"""The bookshelf: the new-book dialog, a continue-hero over the last-touched.

Every flow drives the real stack — browser, API, Postgres — and ends on the
accessibility floor. One test runs that floor with the new-book dialog open,
because focus containment and dialog labels are exactly what a closed page
cannot show. Another stops the real API mid-dialog: a create that cannot
reach the service must keep the dialog (and the typed Titel) where they are
and name the failure inside, not drop the user back onto a dead page.
"""

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.db import testsupport
from app.kernel.db.testsupport import url_for
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.stack import API_URL, WEB_URL

if TYPE_CHECKING:
    from pathlib import Path

    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]


def _create_book(page: Page, title: str, genre: str = "") -> None:
    """Create a novel the only way a user can: through the new-book dialog."""
    page.goto(f"{WEB_URL}/")
    # Scoped to the shelf header's own door: on an empty shelf the drafted
    # panel carries a second "Neues Buch anlegen" CTA, and a page-wide
    # role locator would resolve to both (strict-mode violation). The
    # top bar's header carries no such button, so the header scope names
    # exactly the one door in every shelf state.
    page.locator("header").get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill(title)
    if genre:
        page.get_by_label("Genre", exact=True).fill(genre)
    page.get_by_role("button", name="Anlegen", exact=True).click()


def test_novel_created_in_browser_survives_reload(page: Page, stack: Stack) -> None:
    _create_book(page, "Das Wattenmeer", genre="Fantasy")

    # The shelf card carries what the dialog collected: title, genre, and
    # when the book was last touched. The module's database is shared and
    # its order shuffled, so every test here owns a title no other uses.
    card = page.get_by_role("list").get_by_role("link", name="Das Wattenmeer")
    expect(card).to_be_visible()
    # The drafted card carries the genre on its cover's eyebrow and the
    # touch time as the bare relative word — the named "Zuletzt bearbeitet"
    # line is the hero's, and this book (just created) is the hero. The
    # row — the list item, not the link — is what carries everything the
    # dialog collected.
    row = page.get_by_role("listitem").filter(has_text="Das Wattenmeer")
    expect(row).to_contain_text("Fantasy")
    hero = page.get_by_role("region", name="Aktuell in Arbeit")
    expect(hero).to_contain_text("Das Wattenmeer")
    expect(hero).to_contain_text("Zuletzt bearbeitet")

    page.reload()
    expect(page.get_by_role("listitem").filter(has_text="Das Wattenmeer")).to_contain_text(
        "Fantasy"
    )

    assert_accessible(page)


def test_hero_names_the_last_touched_novel(page: Page, stack: Stack) -> None:
    _create_book(page, "Der erste Wurf")
    _create_book(page, "Der Sturm")

    hero = page.get_by_role("region", name="Aktuell in Arbeit")
    expect(hero).to_be_visible()
    # The newest book is the one to continue; an older one never wins the hero.
    expect(hero).to_contain_text("Der Sturm")
    expect(hero.get_by_text("Der erste Wurf")).to_have_count(0)
    expect(hero).to_contain_text("Zuletzt bearbeitet")

    # The drafted type steps, in computed pixels: the hero's title on the
    # hero step (30 — the drafted resolution text-3xl, carried by --text-hero),
    # the shelf card's title at the title step (20). A class swap that
    # misses the token fails here as a wrong pixel, not as a silent drift.
    sizes = page.evaluate(
        """() => ({
          hero: getComputedStyle(
            document.querySelector('section[aria-label="Aktuell in Arbeit"] h2')
          ).fontSize,
          card: getComputedStyle(document.querySelector('[data-shelf-title]')).fontSize,
        })"""
    )
    assert sizes == {"hero": "30px", "card": "20px"}, sizes

    # The text steps render at the scale, not just in the CSS: a token edit
    # that never reaches a surface fails here as a pixel. The hero's sync
    # line rides the meta step (12); the top bar's place name rides body
    # (14), pinned where the shell owns it.
    steps = page.evaluate(
        """() => {
          const hero = document.querySelector('section[aria-label="Aktuell in Arbeit"]');
          return {
            body: getComputedStyle(document.querySelector('header .truncate')).fontSize,
            meta: getComputedStyle(hero.querySelector('.text-meta')).fontSize,
          };
        }"""
    )
    assert steps == {"body": "14px", "meta": "12px"}, steps
    expect(hero.locator("[data-cover-tone]").first).to_be_visible()
    # The drafted hero door is the primary one: the sepia fill the draft
    # draws on "Weiterschreiben in Kapitel n" is the button ladder's
    # primary paint (the old shelf's links carried no fill — the draft
    # moved this pin, not the behaviour: the door opens the hero's book).
    door = hero.get_by_role("link", name=re.compile(r"Weiterschreiben"))
    expect(door).to_be_visible()
    expect(door).to_have_class(re.compile(r"\bbg-cover-sepia\b"))

    # The hero's link opens the book it names, and the workspace's h1
    # reads the title step (20) — the third pinned size.
    door.click()
    expect(page.get_by_role("heading", name="Der Sturm")).to_be_visible()
    assert (
        page.evaluate("getComputedStyle(document.querySelector('h1.text-title')).fontSize")
        == "20px"
    )

    assert_accessible(page)


def test_writing_a_chapter_makes_its_book_the_hero(page: Page, stack: Stack) -> None:
    """A chapter write is the most common way the hero's truth changes.

    The books come from the API, not the new-book dialog: the dialog's
    mutation invalidates the ["novels"] cache itself, which would mask the
    gap this test pins — the workbench's chapter writes must invalidate it
    too, or the hero names a stale last-touched book for the 30 s staleTime.
    """
    older = page.request.post(f"{API_URL}/api/writing/novels", data={"title": "Die Halligen"})
    assert older.ok, older.text()
    newer = page.request.post(f"{API_URL}/api/writing/novels", data={"title": "Der Strandwall"})
    assert newer.ok, newer.text()

    # The shelf loads, the cache settles: the hero names the newer book.
    # This is the cached truth a returning writer carries in memory.
    page.goto(f"{WEB_URL}/")
    hero = page.get_by_role("region", name="Aktuell in Arbeit")
    expect(hero).to_contain_text("Der Strandwall")

    # Write in the older book through the real workbench: a chapter
    # created, a body typed, the autosave settled.
    page.get_by_role("link", name="Die Halligen").click()
    page.get_by_role("button", name="Neues Kapitel").click()
    editor = page.locator(".ProseMirror")
    editor.click()
    page.keyboard.type("Nebel über dem Watt.")
    expect(page.get_by_text("Gespeichert")).to_be_visible()

    # Back through the app's own link: a client-side navigation, so the
    # query cache is exactly the one the writes above must have
    # invalidated — a page load would destroy it and hide the gap.
    page.get_by_role("link", name="Alle Romane").click()

    # Well inside the 30 s staleTime, the hero names the book written in.
    expect(hero).to_contain_text("Die Halligen")
    expect(hero.get_by_text("Der Strandwall")).to_have_count(0)

    assert_accessible(page)


def test_new_book_dialog_opens_from_the_keyboard(page: Page, stack: Stack) -> None:
    page.goto(f"{WEB_URL}/")
    expect(page.locator("header").get_by_role("button", name="Neues Buch")).to_be_visible()

    # No mouse anywhere: Tab walks the page to the trigger, Enter opens.
    # The drafted shelf added controls ahead of the header doors (nothing
    # in the rail or bar changed), so the walk still finds the door within
    # its rounds — the button's own words are the drafted "Neues Buch
    # anlegen", the one door on a standing shelf.
    for _ in range(16):
        focused = page.evaluate("() => document.activeElement?.textContent ?? ''")
        if focused.strip() == "Neues Buch anlegen":
            break
        page.keyboard.press("Tab")
    page.keyboard.press("Enter")

    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible()
    title = page.get_by_label("Titel")
    expect(title).to_be_visible()
    # The modal takes focus only after it has committed: React Aria moves
    # focus into it from a passive effect, so the dialog can be visible
    # while the trigger still holds focus. Escape is the overlay's own
    # bubble handler (react-aria's useOverlay), not a document listener —
    # pressed before focus is inside, the key never reaches it and is lost.
    # Waiting for the dialog (or a descendant) to own focus is the event's
    # precondition, not a longer deadline.
    expect(page.locator("[role='dialog']:focus, [role='dialog'] :focus")).to_have_count(1)

    # Escape is the dialog's own way out, and the trigger — the element the
    # keyboard came from — is where focus must land again.
    page.keyboard.press("Escape")
    expect(dialog).to_have_count(0)
    expect(page.locator("header").get_by_role("button", name="Neues Buch")).to_be_focused()

    assert_accessible(page)


def test_the_open_dialog_passes_the_accessibility_floor(page: Page, stack: Stack) -> None:
    page.goto(f"{WEB_URL}/")
    page.locator("header").get_by_role("button", name="Neues Buch").click()
    expect(page.get_by_label("Titel")).to_be_visible()

    # The floor runs with the dialog open: containment and labels are the
    # risk, and a closed page would never see them.
    assert_accessible(page)


def test_create_failure_keeps_the_dialog_open_with_its_message(page: Page, stack: Stack) -> None:
    page.goto(f"{WEB_URL}/")
    page.locator("header").get_by_role("button", name="Neues Buch").click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible()
    page.get_by_label("Titel").fill("Der gescheiterte Wurf")

    # The create cannot reach the service — a real condition of a local
    # app, produced by stopping the real API, not by faking a response.
    stack.stop_api()
    try:
        page.get_by_role("button", name="Anlegen", exact=True).click()

        # The dialog stays open, the failure is named where the retry is,
        # and the typed Titel is still the user's to fix or resubmit.
        expect(dialog).to_be_visible()
        expect(dialog.get_by_role("alert")).to_contain_text("konnte nicht angelegt werden")
        expect(page.get_by_label("Titel")).to_have_value("Der gescheiterte Wurf")
    finally:
        stack.start_api()

    assert_accessible(page)


def test_landing_page_reports_an_unreachable_backend(page: Page, stack: Stack) -> None:
    """A local service the user has not started must be named, not shown as empty."""
    page.goto(f"{WEB_URL}/")
    expect(page.locator("header").get_by_role("button", name="Neues Buch")).to_be_visible()

    stack.stop_api()
    try:
        page.reload()
        # The alert is the page's own error message; nothing else claims the role.
        expect(page.get_by_role("alert").filter(has_text="nicht geladen")).to_be_visible()
    finally:
        stack.start_api()

    # The same page recovers once the service answers again.
    page.reload()
    expect(page.locator("header").get_by_role("button", name="Neues Buch")).to_be_visible()

    assert_accessible(page)


def test_landing_page_retry_recovers_without_a_reload(page: Page, stack: Stack) -> None:
    """The dead-backend story has a second act: the retry button, not F5."""
    page.goto(f"{WEB_URL}/")
    expect(page.locator("header").get_by_role("button", name="Neues Buch")).to_be_visible()

    stack.stop_api()
    try:
        page.reload()
        expect(page.get_by_role("alert").filter(has_text="nicht geladen")).to_be_visible()
        expect(page.get_by_role("button", name="Erneut versuchen")).to_be_visible()
    finally:
        stack.start_api()

    # One press, no reload: the shelf is back.
    page.get_by_role("button", name="Erneut versuchen").click()
    expect(page.locator("header").get_by_role("button", name="Neues Buch")).to_be_visible()

    assert_accessible(page)


def _seed_novel(page: Page, title: str) -> dict[str, object]:
    """Create a novel through the API, the way a second device would."""
    response = page.request.post(f"{API_URL}/api/writing/novels", data={"title": title})
    assert response.ok, response.text()
    return response.json()


def _seed_chapter(page: Page, novel_id: str, title: str, body: str = "") -> None:
    """Create a chapter through the API and, when given, write its body.

    The counts the shelf reports are derived from chapter bodies, so the
    seeding must write real prose — whitespace-separated words — not open
    the dialog.
    """
    response = page.request.post(
        f"{API_URL}/api/writing/novels/{novel_id}/chapters",
        data={"title": title},
    )
    assert response.ok, response.text()
    chapter_id = response.json()["id"]
    if body:
        written = page.request.put(
            f"{API_URL}/api/writing/chapters/{chapter_id}", data={"body": body}
        )
        assert written.ok, written.text()


def test_shelf_cards_show_length_in_words_not_percentages(page: Page, stack: Stack) -> None:
    """A card answers "how long is this book?" in chapters and words.

    Four chapters carrying 6 843 words, seeded through the API, must read
    exactly so — and no percentage anywhere: a progress number is a claim
    the shelf never earned.
    """
    novel = _seed_novel(page, "Das Zählwerk")
    for index, words in enumerate([2000, 2000, 2843, 0]):
        _seed_chapter(page, str(novel["id"]), f"Kapitel {index + 1}", "Wort " * words)

    page.goto(f"{WEB_URL}/")
    card = page.get_by_role("list").get_by_role("link", name="Das Zählwerk")
    expect(card).to_be_visible()
    expect(card).to_contain_text("4 Kapitel")
    expect(card).to_contain_text("6.843 Wörter")
    expect(page.get_by_text("%")).to_have_count(0)

    assert_accessible(page)


def test_an_eighty_character_title_keeps_the_card_shape(page: Page, stack: Stack) -> None:
    """A long title wraps inside its span instead of blowing up the shelf.

    The states screen's long-title answer (G-4, `shelf-states.html` panel
    4): no ellipsis cut on the card's title — it wraps typographically,
    the unbreakable token breaks inside its own box, and the full string
    stays the link's accessible name. Measured where it can fail: the
    computed clamp must be "none" (an ellipsis cut is data loss), nothing
    paints past the title's box, and the card keeps the grid's width.
    """
    # The 40-character compound cannot wrap on its own; the title has to
    # break it. No phrase in the title may be one another test in this
    # module queries by (card names match as substrings, and the module's
    # database is shared): an overlap would resolve one test's locator to
    # two cards, by order of the shuffle.
    long_title = "Die Geschichte Nordseeinsellichterturmwegesommerblickea und die Küsten im Herbst"
    assert len(long_title) == 80
    assert "Nordseeinsellichterturmwegesommerblickea" in long_title
    _seed_novel(page, "Der kurze Wurf")
    _seed_novel(page, long_title)

    page.goto(f"{WEB_URL}/")
    shelf = page.get_by_role("list")
    short_card = shelf.get_by_role("link", name="Der kurze Wurf")
    long_card = shelf.get_by_role("link", name=long_title)
    expect(short_card).to_be_visible()
    expect(long_card).to_be_visible()

    long_span = long_card.locator("[data-shelf-title]")
    short_span = short_card.locator("[data-shelf-title]")
    expect(long_span).to_be_visible()
    expect(short_span).to_be_visible()

    # The clamp is really gone — computed, not a class string: the states
    # screen bans the ellipsis on the card's title.
    clamp = long_span.evaluate("element => getComputedStyle(element).webkitLineClamp")
    assert clamp == "none", clamp

    # The unbreakable token wraps inside the span: nothing paints past it.
    overflow = long_span.evaluate("element => element.scrollWidth - element.clientWidth")
    assert overflow <= 1

    # The full string is the link's accessible name — the locator above
    # already matched it, and the span's text is the whole title: no data
    # loss for a reader, whatever the wrap did visually.
    assert long_span.inner_text().startswith(
        "Die Geschichte Nordseeinsellichterturmwegesommerblickea"
    )

    assert_accessible(page)


def test_a_title_only_book_renders_no_placeholders(page: Page, stack: Stack) -> None:
    """A book with nothing but a title still renders a whole card.

    No undefined, no null, and no separator dangling where an absent field
    would be: the optional fields render when they exist and never leave a
    mark. The drafted card carries no meta separator at all — its facts
    are their own rows.
    """
    _seed_novel(page, "Der stille Strand")

    page.goto(f"{WEB_URL}/")
    card = page.get_by_role("list").get_by_role("link", name="Der stille Strand")
    expect(card).to_be_visible()
    expect(card).to_contain_text("0 Kapitel")
    expect(card).to_contain_text("0 Wörter")

    text = card.inner_text()
    assert "undefined" not in text
    assert "null" not in text
    # The drafted rows are separate lines: no separator survives because
    # none is drafted — the counts speak for themselves.
    assert "·" not in text

    assert_accessible(page)


def test_a_failed_refresh_keeps_the_shelf_and_its_retry(page: Page, stack: Stack) -> None:
    """A refused refresh speaks quietly above the standing shelf — and its
    retry retires the note once the answer lands.

    The refusal is the app's own flow: the second create passes (the POST
    is not the refused call) and its invalidation makes the active list ask
    again — the GET is the one refused — so the failure lands on a shelf
    that stands, with the fresh book missing from the cached truth until
    the retry's answer arrives. The gate stays healthy here, so the gate's
    own path into the quiet note is pinned by
    `test_the_quiet_note_cannot_outlive_its_cause`.
    """
    _create_book(page, "Der sichere Hafen")
    # The refusal arms only against a settled shelf: the create's own
    # invalidation refetch must have landed first, or the route would
    # refuse it while the cache still holds the empty list — and the page
    # would show the honest outage for an empty library, not the state
    # under test.
    card = page.get_by_role("list").get_by_role("link", name="Der sichere Hafen")
    expect(card).to_be_visible()
    page.route(
        "**/api/writing/novels",
        lambda route: route.abort() if route.request.method == "GET" else route.fallback(),
    )

    page.locator("header").get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill("Der zweite Hafen")
    page.get_by_role("button", name="Anlegen", exact=True).click()

    # The quiet voice, above the shelf — never the alert, never a torn-down
    # page: the books shown are the last loaded ones.
    note = page.get_by_role("status")
    expect(note).to_contain_text("Die Aktualisierung ist fehlgeschlagen")
    expect(page.get_by_role("link", name="Der sichere Hafen")).to_be_visible()
    expect(page.get_by_role("alert")).to_have_count(0)

    # The way back is the note's own retry — one press, no reload: the note
    # clears, and the shelf answers with what the refresh found.
    page.unroute("**/api/writing/novels")
    note.get_by_role("button", name="Erneut versuchen").click()
    expect(page.get_by_role("status")).to_have_count(0)
    expect(page.get_by_role("link", name="Der zweite Hafen")).to_be_visible()
    expect(page.get_by_role("link", name="Der sichere Hafen")).to_be_visible()

    assert_accessible(page)


def test_the_quiet_note_cannot_outlive_its_cause(page: Page, stack: Stack) -> None:
    """The gate's failure can hold the quiet note over healthy books — and
    the note's retry must retire it, not just refresh the list.

    Only the gate refuses here: the list stays healthy, so a retry that
    asked nothing but the list would succeed and still leave the note
    standing over freshly refreshed books. Pressing it once the service
    answers again has to clear the note — it answers the gate too, or it
    never goes away.
    """
    _create_book(page, "Der leise Anfang")
    shelf_card = page.get_by_role("list").get_by_role("link", name="Der leise Anfang")
    expect(shelf_card).to_be_visible()
    page.route("**/api/setup/status", lambda route: route.abort())

    # Away and back through the app's own links: the remount re-asks the
    # gate, the refusal fails it, and the books — still cached, still
    # standing — hold the quiet note above them.
    shelf_card.click()
    page.get_by_role("link", name="Alle Romane").click()
    note = page.get_by_role("status")
    expect(note).to_contain_text("Die Aktualisierung ist fehlgeschlagen")
    expect(shelf_card).to_be_visible()
    expect(page.get_by_role("alert")).to_have_count(0)

    # The gate answers again; one press retires the note. A retry that
    # refreshed the list alone would succeed here and change nothing —
    # that is the defect this test pins.
    page.unroute("**/api/setup/status")
    note.get_by_role("button", name="Erneut versuchen").click()
    expect(page.get_by_role("status")).to_have_count(0)
    expect(shelf_card).to_be_visible()

    assert_accessible(page)


def test_the_rail_is_the_one_navigation(page: Page, stack: Stack) -> None:
    """The shell offers one map: the rail — the bar carries the place, not links.

    Pinned on the shelf: the Hauptnavigation is visible and the word Wissen
    names exactly one link, the rail's entry. A count of two means a
    capability link has grown back into the top bar, and the app navigates
    from two places again.
    """
    page.goto(f"{WEB_URL}/")
    expect(page.get_by_role("navigation", name="Hauptnavigation")).to_be_visible()
    expect(page.get_by_role("link", name="Wissen")).to_have_count(1)
    # And the banner carries none of it: the rail is the map, the bar is
    # the place — a navigation landmark back inside the banner is a
    # capability link growing back into the bar.
    expect(page.get_by_role("banner").get_by_role("navigation")).to_have_count(0)

    assert_accessible(page)


def test_the_drafted_row_is_reachable_and_operable_by_keyboard(page: Page, stack: Stack) -> None:
    """The drafted filter row works without a mouse — and the axe floor
    runs in both themes on the recomposed shelf.

    Search, genre filter, view toggle and the card's quick menu are all
    native controls in the drafted composition; this pins that the
    keyboard really drives them: typing filters, Enter on the toggle
    switches the view, the menu opens on its trigger and Escape hands
    focus back. The amber ring is the focus contract — pinned on the
    search field as the row's first stop.
    """
    # No phrase in these titles may be one another test in this module
    # queries by (card names match as substrings, and the module's
    # database is shared): an overlap would resolve one test's locator to
    # another test's card.
    _seed_novel(page, "Der Wetterhahn")
    _seed_novel(page, "Die Sundfahrer")
    page.goto(f"{WEB_URL}/")

    # Search: reachable by Tab from the page's head, and the amber ring
    # paints on the field's shell when the keyboard lands on it.
    search = page.get_by_label("Regal durchsuchen")
    search.focus()
    expect(search).to_be_focused()
    ring = page.evaluate(
        """() => {
          const box = document.activeElement;
          const shell = box.closest("div");
          const style = getComputedStyle(shell);
          return { shadow: style.boxShadow };
        }"""
    )
    assert ring["shadow"] != "none", ring
    page.keyboard.type("wetterhahn")
    expect(page.get_by_role("link", name="Der Wetterhahn")).to_be_visible()
    expect(page.get_by_role("link", name="Die Sundfahrer")).to_have_count(0)
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.press("Backspace")
    expect(page.get_by_role("link", name="Die Sundfahrer")).to_be_visible()

    # The view toggle: two named buttons, the grid the drafted default
    # with its pressed state saying so; Enter switches the shelf to its
    # dense rows and back.
    grid = page.get_by_role("button", name="Rasteransicht")
    list = page.get_by_role("button", name="Listenansicht")
    expect(grid).to_have_attribute("aria-pressed", "true")
    expect(list).to_have_attribute("aria-pressed", "false")
    expect(page.locator("[data-shelf-card]").first).to_be_visible()
    list.focus()
    page.keyboard.press("Enter")
    expect(list).to_have_attribute("aria-pressed", "true")
    expect(page.locator("[data-shelf-row]").first).to_be_visible()
    expect(page.locator("[data-shelf-card]")).to_have_count(0)
    grid.focus()
    page.keyboard.press("Enter")
    expect(page.locator("[data-shelf-card]").first).to_be_visible()

    # The card's quick menu: the more_horiz trigger is a named button;
    # Enter opens, the items are real menu items, Escape closes and hands
    # focus back to the trigger.
    trigger = page.get_by_role("button", name="Aktionen für Der Wetterhahn")
    trigger.focus()
    page.keyboard.press("Enter")
    expect(page.get_by_role("menuitem", name="Details")).to_be_visible()
    expect(page.get_by_role("menuitem", name="Exportieren")).to_be_visible()
    expect(page.get_by_role("menuitem", name="Löschen")).to_be_visible()
    expect(page.locator("[role='menu']:focus, [role='menu'] :focus")).to_have_count(1)
    page.keyboard.press("Escape")
    expect(trigger).to_be_focused()

    # The axe floor in both halves of the theme pair: the tokens are
    # `light-dark()`, so the OS preference flips the page without any
    # stored choice, and the recomposed shelf has to pass on both grounds.
    assert_accessible(page)
    page.emulate_media(color_scheme="dark")
    expect(page.locator("[data-cover-tone]").first).to_be_visible()
    assert_accessible(page)
    page.emulate_media(color_scheme="light")

    assert_accessible(page)


def test_header_controls_keep_their_content_inside_the_control(page: Page, stack: Stack) -> None:
    """An icon beside a label is one line: the control's height is its contract.

    The header carries two controls that pair a glyph with a word. Tailwind's
    preflight makes the glyph a block, so a control that lets its children
    flow stacks them: the 28 px box keeps its height and the label lands
    past its bottom edge, over the shelf below. The assertion reads the
    rendered boxes, not the classes — overflow is what a writer sees.
    """
    created = page.request.post(f"{API_URL}/api/writing/novels", data={"title": "Der Knopf"})
    assert created.ok, created.text()
    page.goto(f"{WEB_URL}/")

    # Both controls stand on the standing shelf this test seeds — the
    # draft draws the header strip with its doors on the empty shelf too
    # (`shelf-empty.html`, beside the panel's own CTA), but that
    # composition is pinned by the unit test's empty-state assertion,
    # not exercised here.
    for name in ("Importieren", "Neues Buch anlegen"):
        expect(page.get_by_role("button", name=name)).to_be_visible()

    rows = page.evaluate(
        """() => ["Importieren", "Neues Buch anlegen"].map((name) => {
            const button = [...document.querySelectorAll("button")].find(
                (candidate) => candidate.textContent.trim() === name
            );
            return button === undefined
                ? {name, found: false}
                : {name, found: true,
                   content: button.scrollHeight,
                   height: button.clientHeight};
        })"""
    )

    for row in rows:
        assert row["found"], row
        assert row["content"] <= row["height"], row

    assert_accessible(page)


def _rows(statement: str, params: dict[str, object] | None = None) -> list[tuple[object, ...]]:
    """Rows from the stack's database as plain tuples, in a worker thread.

    The interchange suite's own reader: pytest-asyncio keeps a session loop
    running, and asyncio.run refuses to start a second one in the same thread.
    """
    database = testsupport.test_database("narrare_v2_e2e")

    async def run() -> list[tuple[object, ...]]:
        engine = create_async_engine(url_for(database))
        try:
            async with engine.connect() as connection:
                return [
                    tuple(each) for each in await connection.execute(text(statement), params or {})
                ]
        finally:
            await engine.dispose()

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, run()).result()


def test_export_then_delete_a_novel(page: Page, stack: Stack, tmp_path: Path) -> None:
    """The book's whole arc on the shelf: correct it, warn, export, delete.

    The details dialog renames the book through the card's menu; the delete
    dialog names what dies (chapters and knowledge entries), says documents
    survive, and carries the export line — "never exported" first, the
    fresh truth after the export the dialog itself offered. The confirmed
    delete leaves zero rows in every novel-scoped table of the stack's own
    database, and the shelf without the card.
    """
    novel = _seed_novel(page, "Der letzte Wurf")
    novel_id = str(novel["id"])
    _seed_chapter(page, novel_id, "Kapitel 1", "Ein letzter Satz. ")

    page.goto(f"{WEB_URL}/")
    row = page.get_by_role("listitem").filter(has_text="Der letzte Wurf")
    expect(row).to_be_visible()

    # The details dialog: the card's menu opens it, and the rename lands on
    # the row the next shelf read answers with.
    row.get_by_role("button", name="Aktionen für Der letzte Wurf").click()
    page.get_by_role("menuitem", name="Details").click()
    details = page.get_by_role("dialog", name="Details zum Roman")
    details.get_by_label("Titel").fill("Der allerletzte Wurf")
    details.get_by_role("button", name="Speichern").click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    renamed = page.get_by_role("list").get_by_role("link", name="Der allerletzte Wurf")
    expect(renamed).to_be_visible()

    # The delete dialog warns before it asks: the counts, the documents, and
    # the never-exported line with the export one press away. The delete and
    # export dialogs are named — the export opens stacked over the delete —
    # so every query names the dialog it means.
    row = page.get_by_role("listitem").filter(has_text="Der allerletzte Wurf")
    row.get_by_role("button", name="Aktionen für Der allerletzte Wurf").click()
    page.get_by_role("menuitem", name="Löschen").click()
    dialog = page.get_by_role("dialog", name="Roman löschen")
    expect(dialog).to_contain_text("1 Kapitel")
    expect(dialog).to_contain_text("0 Wissenseinträge")
    expect(dialog).to_contain_text("Dokumente")
    expect(dialog).to_contain_text("noch nie exportiert")
    assert_accessible(page)

    # The export the dialog offers lands in a folder of this run, and its
    # success flips the line the delete was about to judge.
    dialog.get_by_role("button", name="Jetzt exportieren").click()
    export = page.get_by_role("dialog", name=re.compile("exportieren$"))
    export.get_by_label("Zielordner").fill(str(tmp_path / "export"))
    export.get_by_role("button", name="Jetzt exportieren").click()
    expect(export).to_contain_text("Export abgeschlossen")
    export.get_by_role("button", name="Schließen").click()
    expect(export).to_have_count(0)
    expect(dialog).to_contain_text("Seit dem letzten Export unverändert")

    # The confirm is final: the card leaves the shelf and the database
    # holds none of the book's rows — chapters, entities, relations,
    # suggestions, findings all zero, the documents' library untouched.
    dialog.get_by_role("button", name="Löschen").click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(page.get_by_role("link", name="Der allerletzte Wurf")).to_have_count(0)

    for statement in (
        "SELECT 1 FROM chapters WHERE novel_id = :id",
        "SELECT 1 FROM entities WHERE novel_id = :id",
        "SELECT 1 FROM entity_relations edge JOIN entities e ON e.id = edge.from_entity_id"
        " WHERE e.novel_id = :id",
        "SELECT 1 FROM entity_suggestions WHERE novel_id = :id",
        "SELECT 1 FROM consistency_findings WHERE novel_id = :id",
        "SELECT 1 FROM novels WHERE id = :id",
    ):
        assert _rows(statement, {"id": novel_id}) == [], statement

    assert_accessible(page)
