"""Autosave tells the truth about the answer it got.

A refused write is named beside the text and never worn as "saved"; the body
it carried survives in memory, and the next keystroke retries it against the
recovered service — proven on the real stack, outage included. Leaving with
a body that never reached the server asks first: every navigation passes the
flush gate, so the chapter switch, the shelf link and the dock tab ask
through the page's own dialog after their flush fails, and a reload
mid-failure meets the browser's own leave dialog.
"""

import re
from collections.abc import Callable  # noqa: TC003
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Dialog, Page, expect

from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.stack import WEB_URL
from app.kernel.testing.workbench import new_chapter

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]


def _create_book(page: Page, title: str) -> None:
    """Create a novel the only way a user can, then open its workspace.

    The module's database is shared, so every test owns a title no other uses.
    """
    page.goto(f"{WEB_URL}/")
    page.get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill(title)
    page.get_by_role("button", name="Anlegen").click()
    page.get_by_role("link", name=title).click()
    expect(page.get_by_role("heading", name=title)).to_be_visible()


def test_a_refused_save_is_named_and_never_shown_as_saved(page: Page, stack: Stack) -> None:
    """Retain failed text, retry it after recovery and prove it survives a reload."""
    _create_book(page, "Die Bucht")
    new_chapter(page)
    page.locator(".ProseMirror").click()

    stack.stop_api()
    try:
        page.keyboard.type("Der Satz, den niemand speichert.")
        expect(page.get_by_text("Nicht gespeichert", exact=True)).to_be_visible(timeout=10_000)
        expect(page.get_by_text("Gespeichert", exact=True)).to_have_count(0)
    finally:
        stack.start_api()

    page.keyboard.type(" Und noch ein Wort.")
    expect(page.get_by_text("Gespeichert", exact=True)).to_be_visible(timeout=10_000)

    page.reload()
    expect(page.locator(".ProseMirror")).to_contain_text("Und noch ein Wort.")

    assert_accessible(page)


def _answer_leave_guard(page: Page, action: Callable[[], None]) -> None:
    """Run a leave action and answer the page's leave dialog with "Bleiben".

    The ask is the gate's own dialog now (F21), not the browser's: it appears
    once the refused flush has failed, and staying is the answer that keeps
    the work. The action runs first and the dialog is awaited after it — the
    click that starts a blocked navigation returns, and the ask it raised is
    what this helper finds. An action that raises no dialog fails rather than
    passing quietly.
    """
    action()
    leave_dialog = page.get_by_role("dialog")
    expect(leave_dialog).to_be_visible(timeout=10_000)
    leave_dialog.get_by_role("button", name="Bleiben").click()
    expect(leave_dialog).to_have_count(0)


def test_leaving_with_a_failed_save_asks_first(page: Page, stack: Stack) -> None:
    """Protect failed text on chapter switches, links and history navigation."""
    _create_book(page, "Der Priel")
    new_chapter(page)
    new_chapter(page)
    first = page.get_by_role("button", name=re.compile(r"^Kapitel 1\b"))
    first.click()
    expect(first).to_have_attribute("aria-current", "true")
    page.locator(".ProseMirror").click()

    # The outage owns the rest of the proof, and the finally restores the API:
    # pytest-randomly shuffles the module, and whichever test runs next shares
    # this stack — a failure here must not hand it a dead service.
    stack.stop_api()
    try:
        page.keyboard.type("Bleibt hier.")
        expect(page.get_by_text("Nicht gespeichert", exact=True)).to_be_visible(timeout=10_000)

        # Each leave asks through the page's dialog after its flush fails,
        # and a dismissed ask ("Bleiben") keeps the work every time.
        def switch() -> None:
            page.get_by_role("button", name=re.compile(r"^Kapitel 2\b")).click()

        _answer_leave_guard(page, switch)
        expect(page.get_by_role("button", name=re.compile(r"^Kapitel 1\b"))).to_have_attribute(
            "aria-current", "true"
        )
        expect(page.locator(".ProseMirror")).to_contain_text("Bleibt hier.")

        def shelf() -> None:
            page.get_by_role("link", name="Alle Romane").click()

        _answer_leave_guard(page, shelf)
        expect(page.get_by_role("heading", name="Der Priel")).to_be_visible()

        # The shell's chrome is outside this page and a router navigation
        # like any other: the blocker is the one place all of them pass.
        # The rail owns the map since P9 — the bar carries the place, not
        # links — so the door is the rail's Chat entry, the one link the
        # document names Chat.
        def rail() -> None:
            page.get_by_role("link", name="Chat").click()

        _answer_leave_guard(page, rail)
        expect(page.get_by_role("heading", name="Der Priel")).to_be_visible()

        # Back is history, not a click. Driven directly so the assertion is
        # about the blocker, not about Playwright's navigation wait.
        def back() -> None:
            page.evaluate("window.history.back()")

        _answer_leave_guard(page, back)
        expect(page.get_by_role("heading", name="Der Priel")).to_be_visible()
        expect(page.locator(".ProseMirror")).to_contain_text("Bleibt hier.")

        # Opening a dock is a navigation like any other now: the gate asks
        # for the failed body here too, and a dismissed ask keeps the
        # workbench exactly where it was — the dock never opens, the editor
        # keeps the text.
        def dock() -> None:
            page.get_by_role("button", name="Chat", exact=True).click()

        _answer_leave_guard(page, dock)
        expect(page.get_by_role("complementary", name="Chat")).to_have_count(0)
        expect(page.locator(".ProseMirror")).to_contain_text("Bleibt hier.")
    finally:
        stack.start_api()


def test_closing_a_tab_with_a_failed_save_asks(page: Page, stack: Stack) -> None:
    """Prompt on unload only while the chapter contains text the server lacks."""
    _create_book(page, "Der Grund")
    new_chapter(page)
    page.locator(".ProseMirror").click()

    seen: list[str] = []

    def accept(dialog: Dialog) -> None:
        """Record the native dialog and allow the reload to proceed."""
        seen.append(dialog.type)
        dialog.accept()

    page.on("dialog", accept)

    # The negative control first: a clean chapter reloads with no dialog at
    # all, so an unconditional guard cannot pass as a conditional one.
    page.reload()
    expect(page.locator(".ProseMirror")).to_be_visible()
    assert seen == []

    # The reload dropped the caret to <body>; the editor takes it back before
    # the typing — the keyboard alone would write into nothing.
    page.locator(".ProseMirror").click()

    stack.stop_api()
    try:
        page.keyboard.type("Nicht verlieren.")
        expect(page.get_by_text("Nicht gespeichert", exact=True)).to_be_visible(timeout=10_000)

        # A reload leaves the page, and the browser's own dialog answers for
        # the text that never reached the server — the tab-close half of the
        # guard, spoken by the real unload path (page.close skips beforeunload
        # handlers entirely on this build; a reload runs them). Accepting lets
        # the reload through — dismissing would cancel it — and the fresh page
        # loads against the stopped service and names it.
        page.reload()
        expect(page.get_by_role("alert").filter(has_text="konnte nicht geladen")).to_be_visible()
        assert seen == ["beforeunload"]
    finally:
        stack.start_api()


def test_failed_chapter_creation_keeps_the_unsaved_body(page: Page, stack: Stack) -> None:
    """Keep failure and leave protection until a requested new chapter exists."""
    _create_book(page, "Die Sandbank")
    new_chapter(page)
    page.locator(".ProseMirror").click()

    stack.stop_api()
    try:
        page.keyboard.type("Diesen Satz behalten.")
        expect(page.get_by_text("Nicht gespeichert", exact=True)).to_be_visible(timeout=10_000)

        # The create has nowhere to go and says so beside the button. It
        # navigates nothing — the flush gate stands in front of the
        # selection's navigation, and a create that never arrived never
        # navigates — so no ask happens here. The failed body stays named
        # and protected, exactly as before the click.
        page.get_by_role("button", name="Neues Kapitel").click()
        expect(
            page.get_by_role("alert").filter(has_text="Kapitel konnte nicht angelegt")
        ).to_be_visible()
        expect(page.get_by_text("Nicht gespeichert", exact=True)).to_be_visible()
        expect(page.locator(".ProseMirror")).to_contain_text("Diesen Satz behalten.")
        expect(page.get_by_role("button", name=re.compile(r"^Kapitel 1\b"))).to_have_attribute(
            "aria-current", "true"
        )

        # The ask is the page's dialog; dismissal keeps the failed body.
        def shelf() -> None:
            page.get_by_role("link", name="Alle Romane").click()

        _answer_leave_guard(page, shelf)
        expect(page.locator(".ProseMirror")).to_contain_text("Diesen Satz behalten.")
    finally:
        stack.start_api()

    page.locator(".ProseMirror").click()
    page.keyboard.press("End")
    page.keyboard.type(" Jetzt speichern.")
    expect(page.get_by_text("Gespeichert", exact=True)).to_be_visible(timeout=10_000)
    page.get_by_role("button", name="Neues Kapitel").click()
    expect(page.get_by_role("button", name=re.compile(r"^Kapitel 2\b"))).to_have_attribute(
        "aria-current", "true"
    )
    expect(page.get_by_text("Gespeichert", exact=True)).to_have_count(0)
    page.get_by_role("button", name=re.compile(r"^Kapitel 1\b")).click()
    expect(page.locator(".ProseMirror")).to_contain_text("Diesen Satz behalten. Jetzt speichern.")
