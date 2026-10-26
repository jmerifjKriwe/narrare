"""Autosave tells the truth about the answer it got.

A refused write is named beside the text and never worn as "saved"; the body
it carried survives in memory, and the next keystroke retries it against the
recovered service — proven on the real stack, outage included. Leaving with
a body that never reached the server asks first: the chapter switch and the
shelf link confirm after their flush fails, and a reload mid-failure meets
the browser's own leave dialog.
"""

import re
from collections.abc import Callable  # noqa: TC003
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Dialog, Page, expect

from app.kernel.testing.a11y import assert_accessible

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


def test_a_refused_save_is_named_and_never_shown_as_saved(page: Page, stack: Stack) -> None:
    """Retain failed text, retry it after recovery and prove it survives a reload."""
    _create_book(page, "Die Bucht")
    page.get_by_role("button", name="Neues Kapitel").click()
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


def _answer_confirm(page: Page, action: Callable[[], None], *, accept: bool = False) -> str:
    """Run a leave action and answer the native confirm it raises.

    The handler is registered *before* the action on purpose. Playwright's
    click waits for the dialog a handler must answer, so awaiting the event
    around the click deadlocks when the click's own handler raises it: the
    click never returns, so the code that would answer never runs. Registered
    first, the click returns and the wait sees the event that was answered.
    An action that raises no dialog fails rather than passing quietly.
    """
    seen: list[str] = []

    def answer(dialog: Dialog) -> None:
        seen.append(dialog.type)
        if accept:
            dialog.accept()
        else:
            dialog.dismiss()

    page.once("dialog", answer)
    with page.expect_event("dialog", timeout=10_000) as asked:
        action()
    assert seen, "the leave asked nothing"
    return asked.value.type


def test_leaving_with_a_failed_save_asks_first(page: Page, stack: Stack) -> None:
    """Protect failed text on chapter switches, links and history navigation."""
    _create_book(page, "Der Priel")
    page.get_by_role("button", name="Neues Kapitel").click()
    page.get_by_role("button", name="Neues Kapitel").click()
    page.get_by_role("button", name="Kapitel 1", exact=True).click()
    page.locator(".ProseMirror").click()

    # The outage owns the rest of the proof, and the finally restores the API:
    # pytest-randomly shuffles the module, and whichever test runs next shares
    # this stack — a failure here must not hand it a dead service.
    stack.stop_api()
    try:
        page.keyboard.type("Bleibt hier.")
        expect(page.get_by_text("Nicht gespeichert", exact=True)).to_be_visible(timeout=10_000)

        # Each leave asks through window.confirm after its flush fails.
        seen: list[str] = []

        def switch() -> None:
            page.get_by_role("button", name="Kapitel 2", exact=True).click()

        seen.append(_answer_confirm(page, switch))
        expect(page.get_by_role("button", name="Kapitel 1", exact=True)).to_have_attribute(
            "aria-pressed", "true"
        )
        expect(page.locator(".ProseMirror")).to_contain_text("Bleibt hier.")

        def shelf() -> None:
            page.get_by_role("link", name="Alle Romane").click()

        seen.append(_answer_confirm(page, shelf))
        expect(page.get_by_role("heading", name="Der Priel")).to_be_visible()

        # The shell's top bar is outside this page and a router navigation
        # like any other: the blocker is the one place all of them pass.
        def topbar() -> None:
            page.get_by_role("link", name="Chat").click()

        seen.append(_answer_confirm(page, topbar))
        expect(page.get_by_role("heading", name="Der Priel")).to_be_visible()

        # Back is history, not a click. Driven directly so the assertion is
        # about the blocker, not about Playwright's navigation wait.
        def back() -> None:
            page.evaluate("window.history.back()")

        seen.append(_answer_confirm(page, back))
        expect(page.get_by_role("heading", name="Der Priel")).to_be_visible()
        expect(page.locator(".ProseMirror")).to_contain_text("Bleibt hier.")

        # Opening a dock is a navigation inside the book, not a leave: the
        # editor stays mounted, so nothing may be asked here. The dock's own
        # route keeps its tab beside the text.
        page.get_by_role("button", name="Chat", exact=True).click()
        expect(page).to_have_url(re.compile(r"/novels/[^/]+/chat(\?|$)"))
        expect(page.get_by_role("button", name="Chat", exact=True)).to_have_attribute(
            "aria-pressed", "true"
        )

        assert seen == ["confirm", "confirm", "confirm", "confirm"]
    finally:
        stack.start_api()


def test_closing_a_tab_with_a_failed_save_asks(page: Page, stack: Stack) -> None:
    """Prompt on unload only while the chapter contains text the server lacks."""
    _create_book(page, "Der Grund")
    page.get_by_role("button", name="Neues Kapitel").click()
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
    page.get_by_role("button", name="Neues Kapitel").click()
    page.locator(".ProseMirror").click()

    stack.stop_api()
    try:
        page.keyboard.type("Diesen Satz behalten.")
        expect(page.get_by_text("Nicht gespeichert", exact=True)).to_be_visible(timeout=10_000)

        with page.expect_event("dialog") as asked:
            page.once("dialog", lambda dialog: dialog.accept())
            page.get_by_role("button", name="Neues Kapitel").click()
        assert asked.value.type == "confirm"

        expect(
            page.get_by_role("alert").filter(has_text="Kapitel konnte nicht angelegt")
        ).to_be_visible()
        expect(page.get_by_text("Nicht gespeichert", exact=True)).to_be_visible()
        expect(page.locator(".ProseMirror")).to_contain_text("Diesen Satz behalten.")
        expect(page.get_by_role("button", name="Kapitel 1", exact=True)).to_have_attribute(
            "aria-pressed", "true"
        )

        with page.expect_event("dialog") as asked:
            page.once("dialog", lambda dialog: dialog.dismiss())
            page.get_by_role("link", name="Alle Romane").click()
        assert asked.value.type == "confirm"
        expect(page.locator(".ProseMirror")).to_contain_text("Diesen Satz behalten.")
    finally:
        stack.start_api()

    page.locator(".ProseMirror").click()
    page.keyboard.press("End")
    page.keyboard.type(" Jetzt speichern.")
    expect(page.get_by_text("Gespeichert", exact=True)).to_be_visible(timeout=10_000)
    page.get_by_role("button", name="Neues Kapitel").click()
    expect(page.get_by_role("button", name="Kapitel 2", exact=True)).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page.get_by_text("Gespeichert", exact=True)).to_have_count(0)
    page.get_by_role("button", name="Kapitel 1", exact=True).click()
    expect(page.locator(".ProseMirror")).to_contain_text("Diesen Satz behalten. Jetzt speichern.")
