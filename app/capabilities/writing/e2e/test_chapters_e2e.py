"""The writing workbench: autosave, a chapter rail beside the editor, panel state in the URL.

The selection is URL state too: a chapter has an address (`?chapter=`), the
back button walks it, and every switch — rail, history, a dead link — passes
the flush gate. The param-less choice is latched, so a create's refetch can
never move the editor around the gate, and a refused switch asks and keeps
the work on a dismissed ask.

Every flow drives the real stack — browser, API, Postgres — and ends on the
accessibility floor.
"""

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, Route, expect

from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.workbench import new_chapter

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]


def _create_book(page: Page, title: str) -> None:
    """Create a novel the only way a user can, then open its workspace.

    The module's database is shared, so every test owns a title no other uses.
    """
    page.goto("http://127.0.0.1:3100/")
    page.get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill(title)
    page.get_by_role("button", name="Anlegen").click()
    page.get_by_role("link", name=title).click()
    expect(page.get_by_role("heading", name=title)).to_be_visible()


def test_typed_chapter_body_survives_reload(page: Page, stack: Stack) -> None:
    page.goto("http://127.0.0.1:3100/")
    page.get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill("Der Nebel")
    page.get_by_role("button", name="Anlegen").click()

    page.get_by_role("link", name="Der Nebel").click()
    expect(page.get_by_role("heading", name="Der Nebel")).to_be_visible()

    new_chapter(page)
    editor = page.locator(".ProseMirror")
    editor.click()
    page.keyboard.type("Der Nebel kam von See.")

    # No save button: the indicator is the only proof the debounce fired.
    expect(page.get_by_text("Gespeichert")).to_be_visible()

    page.reload()
    expect(page.locator(".ProseMirror")).to_contain_text("Der Nebel kam von See.")

    assert_accessible(page)


def test_rail_sits_beside_the_editor_without_scrolling(page: Page, stack: Stack) -> None:
    _create_book(page, "Die Salzwiese")
    page.get_by_role("button", name="Neues Kapitel").click()

    rail = page.get_by_role("complementary")
    editor = page.locator(".ProseMirror")
    expect(rail).to_be_visible()
    expect(editor).to_be_visible()

    # Beside, not above: the rail ends where the editor begins.
    rail_box = rail.bounding_box()
    editor_box = editor.bounding_box()
    assert rail_box is not None and editor_box is not None
    assert rail_box["x"] + rail_box["width"] <= editor_box["x"]

    # Both fit the viewport at once: writing no longer scrolls past the list.
    viewport = page.viewport_size
    assert viewport is not None
    for box in (rail_box, editor_box):
        assert box["x"] >= 0 and box["x"] + box["width"] <= viewport["width"]
        assert box["y"] >= 0 and box["y"] + box["height"] <= viewport["height"]

    assert_accessible(page)


def test_rail_zero_url_renders_collapsed(page: Page, stack: Stack) -> None:
    _create_book(page, "Das Wrack")
    page.get_by_role("button", name="Neues Kapitel").click()

    # A shared link lands exactly in the state it was shared in.
    page.goto(f"{page.url.split('?')[0]}?rail=0")

    # The editor's visibility proves the page loaded — only then does an
    # absent rail mean "collapsed", not "not rendered yet".
    expect(page.locator(".ProseMirror")).to_be_visible()
    expect(page.get_by_role("complementary")).to_have_count(0)
    # The way back is on the page, not only in the browser's history.
    expect(page.get_by_role("button", name="Kapitelleiste")).to_be_visible()

    assert_accessible(page)


def test_back_button_restores_the_expanded_rail(page: Page, stack: Stack) -> None:
    _create_book(page, "Der Leuchtturm")
    page.get_by_role("button", name="Neues Kapitel").click()
    expect(page.get_by_role("complementary")).to_be_visible()

    page.get_by_role("button", name="Kapitelleiste").click()
    expect(page.get_by_role("complementary")).to_have_count(0)
    # The collapse is a navigation: the state lives in the URL.
    assert "rail=false" in page.url

    page.go_back()
    expect(page.get_by_role("complementary")).to_be_visible()
    expect(page.locator(".ProseMirror")).to_be_visible()

    assert_accessible(page)


def test_typed_text_survives_a_chapter_switch(page: Page, stack: Stack) -> None:
    _create_book(page, "Die Mole")
    new_chapter(page)
    editor = page.locator(".ProseMirror")
    editor.click()
    page.keyboard.type("Erster Satz am Kai.")

    # Switch inside the 800 ms debounce: nothing is written yet and the
    # indicator is quiet (it stays hidden while the save is pending).
    # Waiting for "Gespeichert" here would exercise only the settled path;
    # the unmount flush is what this test is about.
    expect(page.get_by_role("status")).to_have_count(0)

    # The switch is the flush's cue. Wait for its PUT on the wire rather
    # than for a clock: the response is the fact that the pending text
    # reached the server.
    with page.expect_response(
        lambda response: (
            "/api/writing/chapters/" in response.url and response.request.method == "PUT"
        )
    ) as flushed:
        page.get_by_role("button", name="Neues Kapitel").click()
    assert flushed.value.ok

    # A fresh chapter starts empty; the written one keeps its text — and
    # the reload proves the row, not the in-memory body the switch carried.
    expect(page.locator(".ProseMirror")).to_have_text("")
    page.reload()
    page.get_by_role("button", name=re.compile(r"^Kapitel 1\b")).click()
    expect(page.locator(".ProseMirror")).to_contain_text("Erster Satz am Kai.")

    assert_accessible(page)


def test_the_latest_touched_chapter_opens_first(page: Page, stack: Stack) -> None:
    _create_book(page, "Deichgraf")
    new_chapter(page)
    editor = page.locator(".ProseMirror")
    editor.click()
    page.keyboard.type("Kalter Wind.")
    expect(page.get_by_text("Gespeichert")).to_be_visible()

    # The second chapter is not just created later — it is written in later.
    new_chapter(page)
    page.locator(".ProseMirror").click()
    page.keyboard.type("Springflut.")
    expect(page.get_by_text("Gespeichert")).to_be_visible()

    # The reload opens the chapter last written in, not the first one.
    page.reload()
    expect(page.locator(".ProseMirror")).to_contain_text("Springflut.")
    expect(page.locator(".ProseMirror")).not_to_contain_text("Kalter Wind.")

    assert_accessible(page)


def test_back_button_walks_chapters_and_the_switch_flushes(page: Page, stack: Stack) -> None:
    """The selection is a history step: back pops to the previous chapter's
    address, and the switch that left it flushed its body first — the saved
    row is what comes back, not a body kept in memory."""
    _create_book(page, "Die Kehre")
    new_chapter(page)
    new_chapter(page)
    editor = page.locator(".ProseMirror")
    expect(editor).to_have_text("")
    editor.click()
    page.keyboard.type("Der Satz für Kapitel zwei.")

    # Inside the debounce: nothing is on the wire yet, and the indicator
    # stays hidden while the save is pending.
    expect(page.get_by_role("status")).to_have_count(0)

    # The rail switch inside the debounce is the flush's cue. The switch is
    # a navigation now, so the gate awaits the PUT before the URL moves —
    # waited for on the wire, not on a clock.
    with page.expect_response(
        lambda response: (
            "/api/writing/chapters/" in response.url and response.request.method == "PUT"
        )
    ) as flushed:
        page.get_by_role("button", name=re.compile(r"^Kapitel 1\b")).click()
    assert flushed.value.ok
    expect(editor).to_have_text("")

    # Back pops the selection: Kapitel 2's address, with Kapitel 2's text —
    # and the reload proves the row, not memory.
    page.go_back()
    expect(page.locator(".ProseMirror")).to_contain_text("Der Satz für Kapitel zwei.")
    page.reload()
    expect(page.locator(".ProseMirror")).to_contain_text("Der Satz für Kapitel zwei.")

    assert_accessible(page)


def test_a_dead_chapter_param_degrades_to_the_last_touched_and_cleans_the_url(
    page: Page, stack: Stack
) -> None:
    """A link naming a chapter the book does not have degrades, never errors:
    the last-touched chapter opens and the dead value leaves the address —
    by replace, so history never gains a step for the cleanup."""
    _create_book(page, "Das tote Vorzeichen")
    new_chapter(page)
    page.locator(".ProseMirror").click()
    page.keyboard.type("Kalter Wind.")
    expect(page.get_by_text("Gespeichert")).to_be_visible()
    new_chapter(page)
    page.locator(".ProseMirror").click()
    page.keyboard.type("Springflut.")
    expect(page.get_by_text("Gespeichert")).to_be_visible()

    # The dead link is followed from the shelf, so the entry back is a known
    # place and the pin below can name it.
    bare = page.url.split("?")[0]
    page.get_by_role("link", name="Alle Romane").click()
    expect(page).to_have_url("http://127.0.0.1:3100/")
    page.goto(f"{bare}?chapter=00000000-0000-4000-8000-000000000000")
    expect(page.locator(".ProseMirror")).to_contain_text("Springflut.")
    expect(page.locator(".ProseMirror")).not_to_contain_text("Kalter Wind.")
    # The dead value is cleaned from the address — a replace, so the back
    # button's history never gains a step for the cleanup. Back from the
    # cleaned address lands on the shelf; a push would return to the dead
    # param. (The panel params keep their own convention; only the chapter
    # param must go.)
    expect(page).to_have_url(re.compile(r"^(?!.*chapter=).*$"))
    page.go_back()
    expect(page).to_have_url("http://127.0.0.1:3100/")

    assert_accessible(page)


def test_a_bare_arrival_opens_the_last_touched_chapter_and_writes_nothing(
    page: Page, stack: Stack
) -> None:
    """No param is the workbench's own choice: the chapter last written in
    opens, and arrival writes no chapter param — the address never names
    the server's fallback choice, so a reload still proves it."""
    _create_book(page, "Die stille Adresse")
    new_chapter(page)
    page.locator(".ProseMirror").click()
    page.keyboard.type("Kalter Wind.")
    expect(page.get_by_text("Gespeichert")).to_be_visible()
    new_chapter(page)
    page.locator(".ProseMirror").click()
    page.keyboard.type("Springflut.")
    expect(page.get_by_text("Gespeichert")).to_be_visible()

    bare = page.url.split("?")[0]
    page.goto(bare)
    expect(page.locator(".ProseMirror")).to_contain_text("Springflut.")
    expect(page.locator(".ProseMirror")).not_to_contain_text("Kalter Wind.")
    expect(page).to_have_url(re.compile(r"^(?!.*chapter=).*$"))
    # No late write either: the param never appears once the page settled.
    page.wait_for_timeout(300)
    assert "chapter=" not in page.url

    # The dock reads the same fallback the editor opened: extraction offers
    # the chapter on screen — the last written in — not "no chapter". One
    # truth, and still nothing written to the URL.
    page.get_by_role("button", name="Wissen", exact=True).click()
    dock = page.get_by_role("complementary", name="Wissen")
    expect(dock).to_be_visible()
    expect(dock.get_by_role("button", name="Dieses Kapitel durchsuchen")).to_be_visible()
    expect(dock.get_by_text("Kein aktives Kapitel")).to_have_count(0)
    assert "chapter=" not in page.url

    assert_accessible(page)


def test_a_param_less_create_never_flips_the_editor_past_the_gate(page: Page, stack: Stack) -> None:
    """The param-less selection is latched: a create's refetch makes the new
    chapter the latest, and that may never move the editor by itself. The
    switch is the gated navigation — its flush carries the pending body —
    so the typed text lands in its own row, not nowhere."""
    _create_book(page, "Die Kehrseite")
    page.get_by_role("button", name="Neues Kapitel").click()
    # The selection's address lands after the create's refetch — waited for,
    # so the pop below has a settled entry to pop to.
    expect(page).to_have_url(re.compile(r"chapter="))

    # Back to the param-less address: the workbench keeps the chapter it
    # opened, the way the latch held it.
    page.go_back()
    editor = page.locator(".ProseMirror")
    expect(editor).to_be_visible()
    editor.click()
    page.keyboard.type("Der zu rettende Satz.")
    # Debounce pending: nothing on the wire yet.
    expect(page.get_by_role("status")).to_have_count(0)

    # The create refetches the list, the new chapter becomes the latest —
    # and the switch to it still passes the gate: the flush PUT is awaited
    # on the wire before the editor moves.
    with page.expect_response(
        lambda response: (
            "/api/writing/chapters/" in response.url and response.request.method == "PUT"
        )
    ) as flushed:
        page.get_by_role("button", name="Neues Kapitel").click()
    assert flushed.value.ok
    expect(editor).to_have_text("")

    # The typed text reached Kapitel 1's row — the reload proves the row,
    # not memory, and the new chapter's editor starts empty.
    page.get_by_role("button", name=re.compile(r"^Kapitel 1\b")).click()
    expect(page.locator(".ProseMirror")).to_contain_text("Der zu rettende Satz.")
    page.reload()
    expect(page.locator(".ProseMirror")).to_contain_text("Der zu rettende Satz.")

    assert_accessible(page)


def test_a_refused_switch_to_a_created_chapter_asks_and_dismissal_keeps(
    page: Page, stack: Stack
) -> None:
    """A create whose gate flush is refused asks, and a dismissed ask keeps
    the workbench exactly as it was: the typed text in its editor, the old
    chapter current, the new chapter waiting in the rail unselected."""
    _create_book(page, "Die Sanduhr")
    page.get_by_role("button", name="Neues Kapitel").click()
    # The selection's address lands after the create's refetch.
    expect(page).to_have_url(re.compile(r"chapter="))
    # Back to the param-less address; the editor keeps the chapter.
    page.go_back()
    editor = page.locator(".ProseMirror")

    # The write is refused while the debounce runs.
    stack.stop_api()
    try:
        editor.click()
        page.keyboard.type("Bleibt stehen.")
        expect(page.get_by_text("Nicht gespeichert", exact=True)).to_be_visible(timeout=10_000)
    finally:
        stack.start_api()

    # The create succeeds, but the switch's flush is cut off at the wire —
    # the real condition the PUT meets when the write cannot land. The gate
    # asks through the page's own dialog, the ask is dismissed ("Bleiben"),
    # and nothing moved.
    def cut_writes(route: Route) -> None:
        if route.request.method == "PUT":
            route.abort()
        else:
            route.continue_()

    page.route("**/api/writing/chapters/**", cut_writes)
    try:
        page.get_by_role("button", name="Neues Kapitel").click()
        leave_dialog = page.get_by_role("dialog")
        expect(leave_dialog).to_be_visible(timeout=10_000)
        leave_dialog.get_by_role("button", name="Bleiben").click()
        expect(leave_dialog).to_have_count(0)
        expect(editor).to_contain_text("Bleibt stehen.")
        expect(page.get_by_text("Nicht gespeichert", exact=True)).to_be_visible()
        expect(page.get_by_role("button", name=re.compile(r"^Kapitel 1\b"))).to_have_attribute(
            "aria-current", "true"
        )
        expect(page.get_by_role("button", name=re.compile(r"^Kapitel 2\b"))).not_to_have_attribute(
            "aria-current", "true"
        )
    finally:
        page.unroute("**/api/writing/chapters/**", cut_writes)

    # The body survived the dismissal: the next write carries it.
    editor.click()
    page.keyboard.press("End")
    page.keyboard.type(" Und weiter.")
    expect(page.get_by_text("Gespeichert", exact=True)).to_be_visible(timeout=10_000)

    assert_accessible(page)


def test_the_workbench_names_a_book_it_cannot_load(page: Page, stack: Stack) -> None:
    """An unreachable book is an error with a retry, never an empty workbench."""
    _create_book(page, "Das erreichbare Buch")
    url = page.url  # the real workspace URL, for the recovery half

    # The workbench cannot reach the service — a real condition of a local
    # app, produced by stopping the real API, not by faking a response.
    stack.stop_api()
    try:
        page.goto(url)
        expect(page.get_by_role("alert").filter(has_text="konnte nicht geladen")).to_be_visible()
        expect(page.get_by_role("button", name="Erneut versuchen")).to_be_visible()
    finally:
        stack.start_api()

    # One press, no reload: the workbench is back.
    page.get_by_role("button", name="Erneut versuchen").click()
    expect(page.get_by_role("heading", name="Das erreichbare Buch")).to_be_visible()

    assert_accessible(page)


def test_the_outage_stays_reachable_at_a_narrow_window(page: Page, stack: Stack) -> None:
    """Below 1024 the rail is an overlay — but the overlay exists only when
    the rail does: the loading and outage states get no scrim and nothing
    inert, or the retry the outage names would be unreachable behind a
    drawer that is not there (F22's own edge)."""
    _create_book(page, "Die Enge")
    page.set_viewport_size({"width": 360, "height": 720})
    url = page.url

    stack.stop_api()
    try:
        page.goto(url)
        retry = page.get_by_role("button", name="Erneut versuchen")
        expect(retry).to_be_visible()
        # No drawer stands, so nothing may stand before it: no scrim exists
        # (the scrims are the page's only aria-hidden divs) and the click
        # lands — Playwright refuses a click another element intercepts.
        expect(page.locator("div[aria-hidden='true']")).to_have_count(0)
        retry.click()
        expect(page.get_by_role("alert").filter(has_text="konnte nicht geladen")).to_be_visible()
    finally:
        stack.start_api()

    # The recovery is one press, exactly where it was named.
    page.get_by_role("button", name="Erneut versuchen").click()
    expect(page.get_by_role("heading", name="Die Enge")).to_be_visible()

    assert_accessible(page)


def test_the_workbench_names_a_book_that_does_not_exist(page: Page, stack: Stack) -> None:
    """A 404 is the same honesty: the error copy, not an empty chapter rail."""
    page.goto("http://127.0.0.1:3100/novels/00000000-0000-4000-8000-000000000000")
    expect(page.get_by_role("alert").filter(has_text="konnte nicht geladen")).to_be_visible()
    # The empty-rail copy is a loaded book's truth, not a missing one's.
    expect(page.get_by_text("Noch kein Kapitel")).not_to_be_visible()

    # The retry says the same thing: the book is still not there.
    page.get_by_role("button", name="Erneut versuchen").click()
    expect(page.get_by_role("alert").filter(has_text="konnte nicht geladen")).to_be_visible()

    assert_accessible(page)


def test_chapter_creation_failure_is_named_in_the_rail(page: Page, stack: Stack) -> None:
    """A chapter create that cannot reach the service names itself, never nothing."""
    _create_book(page, "Die Brandung")

    stack.stop_api()
    try:
        page.get_by_role("button", name="Neues Kapitel").click()
        # The create has nowhere to go: the rail says so, beside the button.
        expect(page.get_by_role("alert").filter(has_text="konnte nicht angelegt")).to_be_visible()
    finally:
        stack.start_api()

    # The retry is the same button, once the service answers again.
    page.get_by_role("button", name="Neues Kapitel").click()
    expect(page.get_by_role("button", name=re.compile(r"^Kapitel 1\b"))).to_be_visible()

    assert_accessible(page)


def test_the_rail_names_its_chapter_and_walks_by_keyboard(page: Page, stack: Stack) -> None:
    """The open chapter is named by aria-current — never aria-pressed — the
    rail has exactly one tab stop (the current row), and Up/Down walk the
    rows (Review Focus 2). The walk moves focus, never the selection: the
    chapter changes when a row is activated, not when it is walked past."""
    _create_book(page, "Das Verzeichnis")
    for _ in range(3):
        new_chapter(page)

    rail = page.get_by_role("complementary")
    first = rail.get_by_role("button", name=re.compile(r"^Kapitel 1\b"))
    second = rail.get_by_role("button", name=re.compile(r"^Kapitel 2\b"))
    third = rail.get_by_role("button", name=re.compile(r"^Kapitel 3\b"))

    # The open chapter is aria-current, and nothing wears the toggle state a
    # chapter selection is not (spec §8.9).
    expect(third).to_have_attribute("aria-current", "true")
    expect(third).not_to_have_attribute("aria-pressed", "true")

    # One tab stop: the current row holds tabindex 0, every other row -1.
    expect(third).to_have_attribute("tabindex", "0")
    expect(first).to_have_attribute("tabindex", "-1")
    # The list is its own scroll container (Review Focus 2): a long book
    # scrolls inside the list, never the drawer and never the page.
    expect(rail.get_by_role("list")).to_have_css("overflow-y", "auto")

    # Up/Down walk the rows from wherever the focus sits.
    first.focus()
    page.keyboard.press("ArrowDown")
    walked: object = page.evaluate("document.activeElement && document.activeElement.textContent")
    assert isinstance(walked, str) and walked.startswith("Kapitel 2")
    # The walk left the selection alone.
    expect(third).to_have_attribute("aria-current", "true")
    page.keyboard.press("ArrowUp")
    walked = page.evaluate("document.activeElement && document.activeElement.textContent")
    assert isinstance(walked, str) and walked.startswith("Kapitel 1")

    # The tab stop follows the walk (APG): tab away from the walked row and
    # one shift-tab returns to it — not to the row the selection names.
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Tab")
    left: object = page.evaluate("document.activeElement && document.activeElement.textContent")
    assert isinstance(left, str) and left.startswith("Neues Kapitel")
    page.keyboard.press("Shift+Tab")
    returned: object = page.evaluate("document.activeElement && document.activeElement.textContent")
    assert isinstance(returned, str) and returned.startswith("Kapitel 2")
    # Activating a row ends the walk: the tab stop is the selection's again.
    page.keyboard.press("Enter")
    expect(second).to_have_attribute("aria-current", "true")

    assert_accessible(page)


def test_an_empty_book_shows_its_empty_state(page: Page, stack: Stack) -> None:
    """A book with no chapters shows the empty state, never an empty editor
    card (Review Focus 3)."""
    _create_book(page, "Das leere Buch")

    expect(page.get_by_text("Noch kein Kapitel")).to_be_visible()
    expect(page.locator(".ProseMirror")).to_have_count(0)

    assert_accessible(page)


def test_the_workbench_names_the_chapter_and_counts_its_words(page: Page, stack: Stack) -> None:
    """The runhead names book and chapter beside the save state; the footer
    counts the chapter's words and names its position in the book. The count
    is the shared rule's (R31): the number the server would report, live —
    one word typed, one word in the footer."""
    _create_book(page, "Das Zählwerk")
    for _ in range(4):
        new_chapter(page)
    second = page.get_by_role("button", name=re.compile(r"^Kapitel 2\b"))
    second.click()
    expect(second).to_have_attribute("aria-current", "true")
    address = re.search(r"chapter=([0-9a-f-]+)", page.url)
    assert address is not None, f"the selection never got an address: {page.url}"
    chapter_id = address.group(1)

    # 2107 words arrive the only way words arrive — the real API — so the
    # footer must group thousands the way German reads them.
    verdict: object = page.evaluate(
        """async ([id, body]) => {
          const answer = await fetch(`/api/writing/chapters/${id}`, {
            method: "PUT",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ body }),
          });
          return answer.ok;
        }""",
        [chapter_id, " ".join(["Wort"] * 2107)],
    )
    assert verdict is True

    page.reload()
    expect(page.locator(".ProseMirror")).to_contain_text("Wort")

    # The runhead: book · chapter on the left, the save state on the right —
    # the save state is the runhead's, so typing proves it lives there.
    expect(page.get_by_text("Das Zählwerk · Kapitel 2")).to_be_visible()
    # The footer: the chapter's word count and its position in the book.
    expect(page.get_by_text("2.107 Wörter")).to_be_visible()
    expect(page.get_by_text("Kapitel 2 von 4")).to_be_visible()

    editor = page.locator(".ProseMirror")
    editor.click()
    page.keyboard.press("Control+End")
    page.keyboard.type(" Mehr.")
    expect(page.get_by_text("Gespeichert")).to_be_visible(timeout=10_000)
    # The count is the live document's, not the stored row's.
    expect(page.get_by_text("2.108 Wörter")).to_be_visible()

    assert_accessible(page)
