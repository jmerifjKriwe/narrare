"""The bookshelf: the new-book dialog, a continue-hero over the last-touched.

Every flow drives the real stack — browser, API, Postgres — and ends on the
accessibility floor. One test runs that floor with the new-book dialog open,
because focus containment and dialog labels are exactly what a closed page
cannot show. Another stops the real API mid-dialog: a create that cannot
reach the service must keep the dialog (and the typed Titel) where they are
and name the failure inside, not drop the user back onto a dead page.
"""

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

    # The hero's link opens the book it names.
    hero.get_by_role("link", name="Weiterschreiben").click()
    expect(page.get_by_role("heading", name="Der Sturm")).to_be_visible()

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
