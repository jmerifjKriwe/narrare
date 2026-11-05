"""The bookshelf: the new-book dialog, a continue-hero over the last-touched.

Every flow drives the real stack — browser, API, Postgres — and ends on the
accessibility floor. One test runs that floor with the new-book dialog open,
because focus containment and dialog labels are exactly what a closed page
cannot show. Another stops the real API mid-dialog: a create that cannot
reach the service must keep the dialog (and the typed Titel) where they are
and name the failure inside, not drop the user back onto a dead page.
"""

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.kernel.testing.a11y import assert_accessible

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]


def _create_book(page: Page, title: str, genre: str = "") -> None:
    """Create a novel the only way a user can: through the new-book dialog."""
    page.goto("http://127.0.0.1:3100/")
    page.get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill(title)
    if genre:
        page.get_by_label("Genre").fill(genre)
    page.get_by_role("button", name="Anlegen").click()


def test_novel_created_in_browser_survives_reload(page: Page, stack: Stack) -> None:
    _create_book(page, "Das Wattenmeer", genre="Fantasy")

    # The shelf card carries what the dialog collected: title, genre, and
    # when the book was last touched. The module's database is shared and
    # its order shuffled, so every test here owns a title no other uses.
    card = page.get_by_role("list").get_by_role("link", name="Das Wattenmeer")
    expect(card).to_be_visible()
    expect(card).to_contain_text("Fantasy")
    expect(card).to_contain_text("Zuletzt bearbeitet")

    page.reload()
    expect(page.get_by_role("list").get_by_role("link", name="Das Wattenmeer")).to_contain_text(
        "Fantasy"
    )

    assert_accessible(page)


def test_hero_names_the_last_touched_novel(page: Page, stack: Stack) -> None:
    _create_book(page, "Der erste Wurf")
    _create_book(page, "Der Sturm")

    hero = page.get_by_role("region", name="Mach weiter")
    expect(hero).to_be_visible()
    # The newest book is the one to continue; an older one never wins the hero.
    expect(hero).to_contain_text("Der Sturm")
    expect(hero.get_by_text("Der erste Wurf")).to_have_count(0)
    expect(hero).to_contain_text("Zuletzt bearbeitet")

    # R47's hero steps on the shelf, in computed pixels: the hero's book
    # title reads at the hero step (28), the shelf card's title at emph
    # (15). A class swap that misses the token fails here as a wrong
    # pixel, not as a silent drift. The hero keeps its face and its quiet
    # door, too: the cover tile (any of the three token tones) and the
    # secondary Weiterschreiben — the shelf's links carry no primary fill.
    sizes = page.evaluate(
        """() => ({
          hero: getComputedStyle(document.querySelector('.text-hero')).fontSize,
          card: getComputedStyle(document.querySelector('[data-shelf-title]')).fontSize,
        })"""
    )
    assert sizes == {"hero": "28px", "card": "15px"}, sizes
    expect(hero.locator("div.bg-rule, div.bg-primary, div.bg-foreground").first).to_be_visible()
    door = hero.get_by_role("link", name="Weiterschreiben")
    expect(door).to_be_visible()
    expect(door).not_to_have_class(re.compile(r"bg-primary"))

    # The hero's link opens the book it names, and the workspace's h1
    # reads the title step (20) — the third of R47's pinned sizes.
    hero.get_by_role("link", name="Weiterschreiben").click()
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
    older = page.request.post(
        "http://127.0.0.1:8000/api/writing/novels", data={"title": "Die Halligen"}
    )
    assert older.ok, older.text()
    newer = page.request.post(
        "http://127.0.0.1:8000/api/writing/novels", data={"title": "Der Strandwall"}
    )
    assert newer.ok, newer.text()

    # The shelf loads, the cache settles: the hero names the newer book.
    # This is the cached truth a returning writer carries in memory.
    page.goto("http://127.0.0.1:3100/")
    hero = page.get_by_role("region", name="Mach weiter")
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
    page.goto("http://127.0.0.1:3100/")
    expect(page.get_by_role("button", name="Neues Buch")).to_be_visible()

    # No mouse anywhere: Tab walks the page to the trigger, Enter opens.
    for _ in range(12):
        focused = page.evaluate("() => document.activeElement?.textContent ?? ''")
        if focused.strip() == "Neues Buch":
            break
        page.keyboard.press("Tab")
    page.keyboard.press("Enter")

    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible()
    expect(page.get_by_label("Titel")).to_be_visible()

    # Escape is the dialog's own way out, and the trigger — the element the
    # keyboard came from — is where focus must land again.
    page.keyboard.press("Escape")
    expect(dialog).to_have_count(0)
    expect(page.get_by_role("button", name="Neues Buch")).to_be_focused()

    assert_accessible(page)


def test_the_open_dialog_passes_the_accessibility_floor(page: Page, stack: Stack) -> None:
    page.goto("http://127.0.0.1:3100/")
    page.get_by_role("button", name="Neues Buch").click()
    expect(page.get_by_label("Titel")).to_be_visible()

    # The floor runs with the dialog open: containment and labels are the
    # risk, and a closed page would never see them.
    assert_accessible(page)


def test_create_failure_keeps_the_dialog_open_with_its_message(page: Page, stack: Stack) -> None:
    page.goto("http://127.0.0.1:3100/")
    page.get_by_role("button", name="Neues Buch").click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible()
    page.get_by_label("Titel").fill("Der gescheiterte Wurf")

    # The create cannot reach the service — a real condition of a local
    # app, produced by stopping the real API, not by faking a response.
    stack.stop_api()
    try:
        page.get_by_role("button", name="Anlegen").click()

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
    page.goto("http://127.0.0.1:3100/")
    expect(page.get_by_role("button", name="Neues Buch")).to_be_visible()

    stack.stop_api()
    try:
        page.reload()
        # The alert is the page's own error message; nothing else claims the role.
        expect(page.get_by_role("alert").filter(has_text="nicht geladen")).to_be_visible()
    finally:
        stack.start_api()

    # The same page recovers once the service answers again.
    page.reload()
    expect(page.get_by_role("button", name="Neues Buch")).to_be_visible()

    assert_accessible(page)


def test_landing_page_retry_recovers_without_a_reload(page: Page, stack: Stack) -> None:
    """The dead-backend story has a second act: the retry button, not F5."""
    page.goto("http://127.0.0.1:3100/")
    expect(page.get_by_role("button", name="Neues Buch")).to_be_visible()

    stack.stop_api()
    try:
        page.reload()
        expect(page.get_by_role("alert").filter(has_text="nicht geladen")).to_be_visible()
        expect(page.get_by_role("button", name="Erneut versuchen")).to_be_visible()
    finally:
        stack.start_api()

    # One press, no reload: the shelf is back.
    page.get_by_role("button", name="Erneut versuchen").click()
    expect(page.get_by_role("button", name="Neues Buch")).to_be_visible()

    assert_accessible(page)


def _seed_novel(page: Page, title: str) -> dict[str, object]:
    """Create a novel through the API, the way a second device would."""
    response = page.request.post("http://127.0.0.1:8000/api/writing/novels", data={"title": title})
    assert response.ok, response.text()
    return response.json()


def _seed_chapter(page: Page, novel_id: str, title: str, body: str = "") -> None:
    """Create a chapter through the API and, when given, write its body.

    The counts the shelf reports are derived from chapter bodies, so the
    seeding must write real prose — whitespace-separated words — not open
    the dialog.
    """
    response = page.request.post(
        f"http://127.0.0.1:8000/api/writing/novels/{novel_id}/chapters",
        data={"title": title},
    )
    assert response.ok, response.text()
    chapter_id = response.json()["id"]
    if body:
        written = page.request.put(
            f"http://127.0.0.1:8000/api/writing/chapters/{chapter_id}", data={"body": body}
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

    page.goto("http://127.0.0.1:3100/")
    card = page.get_by_role("list").get_by_role("link", name="Das Zählwerk")
    expect(card).to_be_visible()
    expect(card).to_contain_text("4 Kapitel")
    expect(card).to_contain_text("6.843 Wörter")
    expect(page.get_by_text("%")).to_have_count(0)

    assert_accessible(page)


def test_an_eighty_character_title_keeps_the_card_shape(page: Page, stack: Stack) -> None:
    """A long title clamps inside its span instead of blowing up the shelf.

    Measured where it can fail: the clamp is read from the computed style
    (three lines, not a class string), the unbreakable token must wrap
    inside its own box, and the two title spans — not the cards, the grid
    stretch would equalize the cards either way — must be the same height.
    """
    # The 40-character compound cannot wrap on its own; the span has to
    # break it. No phrase in the title may be one another test in this
    # module queries by (card names match as substrings, and the module's
    # database is shared): an overlap would resolve one test's locator to
    # two cards, by order of the shuffle.
    long_title = "Die Geschichte Nordseeinsellichterturmwegesommerblickea und die Küsten im Herbst"
    assert len(long_title) == 80
    assert "Nordseeinsellichterturmwegesommerblickea" in long_title
    _seed_novel(page, "Der kurze Wurf")
    _seed_novel(page, long_title)

    page.goto("http://127.0.0.1:3100/")
    shelf = page.get_by_role("list")
    short_card = shelf.get_by_role("link", name="Der kurze Wurf")
    long_card = shelf.get_by_role("link", name=long_title)
    expect(short_card).to_be_visible()
    expect(long_card).to_be_visible()

    long_span = long_card.locator("[data-shelf-title]")
    short_span = short_card.locator("[data-shelf-title]")
    expect(long_span).to_be_visible()
    expect(short_span).to_be_visible()

    # The clamp is really three lines, computed — not a class string.
    clamp = long_span.evaluate("element => getComputedStyle(element).webkitLineClamp")
    assert clamp == "3"

    # The unbreakable token wraps inside the span: nothing paints past it.
    overflow = long_span.evaluate("element => element.scrollWidth - element.clientWidth")
    assert overflow <= 1

    # The title slot is fixed at three lines whether the title fills it or
    # not — measured on the spans, the thing the design fixes.
    long_height = long_span.bounding_box()
    short_height = short_span.bounding_box()
    assert long_height is not None and short_height is not None
    assert abs(long_height["height"] - short_height["height"]) <= 1

    assert_accessible(page)


def test_a_title_only_book_renders_no_placeholders(page: Page, stack: Stack) -> None:
    """A book with nothing but a title still renders a whole card.

    No undefined, no null, and no separator dangling where a genre would
    be: the optional fields render when they exist and never leave a mark.
    """
    _seed_novel(page, "Der stille Strand")

    page.goto("http://127.0.0.1:3100/")
    card = page.get_by_role("list").get_by_role("link", name="Der stille Strand")
    expect(card).to_be_visible()
    expect(card).to_contain_text("0 Kapitel")
    expect(card).to_contain_text("0 Wörter")

    text = card.inner_text()
    assert "undefined" not in text
    assert "null" not in text
    # Exactly one separator, and it sits between the two counts.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    assert "0 Kapitel · 0 Wörter" in lines
    assert sum(line.count("·") for line in lines) == 1

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

    page.get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill("Der zweite Hafen")
    page.get_by_role("button", name="Anlegen").click()

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
    page.goto("http://127.0.0.1:3100/")
    expect(page.get_by_role("navigation", name="Hauptnavigation")).to_be_visible()
    expect(page.get_by_role("link", name="Wissen")).to_have_count(1)
    # And the banner carries none of it: the rail is the map, the bar is
    # the place — a navigation landmark back inside the banner is a
    # capability link growing back into the bar.
    expect(page.get_by_role("banner").get_by_role("navigation")).to_have_count(0)

    assert_accessible(page)
