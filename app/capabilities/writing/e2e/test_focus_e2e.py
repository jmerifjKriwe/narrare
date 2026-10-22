"""Progressive focus: F9 deepens the workbench step by step, Esc walks it back.

The depth lives in the URL, the keyboard is a first-class way in and out, and
every depth still passes the accessibility floor. Real stack throughout —
browser, API, Postgres.
"""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.kernel.testing.a11y import assert_accessible

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

# The page's tabbables at the deepest step, from the DOM the workbench keeps:
# buttons, links, fields and the contenteditable editor itself.
_INTERACTIVE = (
    "document.activeElement instanceof HTMLElement"
    " && document.activeElement !== document.body"
    " && document.activeElement.matches("
    "\"button, [href], input, select, textarea, [contenteditable='true']\")"
)


def _open_workbench(page: Page, title: str) -> None:
    """Create a novel the only way a user can, open it, and start writing.

    The module's database is shared, so every test owns a title no other uses.
    """
    page.goto("http://127.0.0.1:3100/")
    page.get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill(title)
    page.get_by_role("button", name="Anlegen").click()
    page.get_by_role("link", name=title).click()
    expect(page.get_by_role("heading", name=title)).to_be_visible()
    page.get_by_role("button", name="Neues Kapitel").click()
    editor = page.locator(".ProseMirror")
    editor.click()
    page.keyboard.type("Erster Satz im Fokus.")
    expect(page.get_by_text("Gespeichert")).to_be_visible()


def test_keyboard_only_focus_cycle(page: Page, stack: Stack) -> None:
    _open_workbench(page, "Die Stilllegung")
    editor = page.locator(".ProseMirror")

    # Depth 0: the workbench as it has always been — rail, chrome, the
    # affordance that offers the first step.
    expect(page.get_by_role("complementary")).to_be_visible()
    expect(page.get_by_role("banner")).to_be_visible()
    expect(page.get_by_role("button", name="Ablenkungen ausblenden")).to_be_visible()
    assert_accessible(page)

    # F9 hides the panels: the rail yields whatever ?rail says, the chrome
    # stays, and the depth becomes URL state.
    page.keyboard.press("F9")
    expect(page.get_by_role("complementary")).to_have_count(0)
    expect(page.get_by_role("banner")).to_be_visible()
    expect(page.get_by_role("button", name="Ablenkungen einblenden")).to_be_visible()
    assert "focus=1" in page.url
    assert_accessible(page)

    # F9 again: chrome-free. Only the writing surface and its save controls.
    page.keyboard.press("F9")
    expect(page.get_by_role("banner")).to_have_count(0)
    assert "focus=2" in page.url
    assert_accessible(page)

    # The keyboard still reaches the page: Tab lands on something interactive
    # (the editor or the one button left), never outside the document.
    page.evaluate("document.activeElement && document.activeElement.blur()")
    page.keyboard.press("Tab")
    assert page.evaluate(f"() => {_INTERACTIVE}")

    # A third F9 is a no-op at the deepest step: still no chrome.
    page.keyboard.press("F9")
    expect(page.get_by_role("banner")).to_have_count(0)

    # Esc walks it back one step at a time: the chrome first …
    page.keyboard.press("Escape")
    expect(page.get_by_role("banner")).to_be_visible()
    assert_accessible(page)

    # … then the rail, back to the state the URL held all along.
    page.keyboard.press("Escape")
    expect(page.get_by_role("complementary")).to_be_visible()
    assert_accessible(page)

    # Esc at the shallow end is a no-op: it must not navigate back or leave
    # the page — the text is the proof the workbench never moved.
    page.keyboard.press("Escape")
    expect(page.get_by_role("heading", name="Die Stilllegung")).to_be_visible()
    expect(editor).to_contain_text("Erster Satz im Fokus.")
    assert_accessible(page)


def test_focus_two_url_renders_chrome_free(page: Page, stack: Stack) -> None:
    _open_workbench(page, "Das Fahrwasser")

    # A shared link lands exactly in the state it was shared in.
    page.goto(f"{page.url.split('?')[0]}?focus=2")

    expect(page.locator(".ProseMirror")).to_be_visible()
    expect(page.get_by_role("banner")).to_have_count(0)
    expect(page.get_by_role("complementary")).to_have_count(0)
    # The affordance is gone at the deepest step: the keyboard is the way
    # back, and nothing on the page pretends otherwise.
    expect(page.get_by_role("button", name="Ablenkungen ausblenden")).to_have_count(0)
    expect(page.get_by_role("button", name="Ablenkungen einblenden")).to_have_count(0)
    assert_accessible(page)

    # And the way back works from a direct render too.
    page.keyboard.press("Escape")
    expect(page.get_by_role("banner")).to_be_visible()
    assert_accessible(page)


def test_chrome_returns_when_leaving_the_novel(page: Page, stack: Stack) -> None:
    _open_workbench(page, "Der Leitdamm")
    # Panels away, chrome still there: depth 1.
    page.goto(f"{page.url.split('?')[0]}?focus=1")
    # The editor's visibility proves the page loaded — only then does an
    # absent rail mean "hidden by focus", not "not rendered yet".
    expect(page.locator(".ProseMirror")).to_be_visible()
    expect(page.get_by_role("complementary")).to_have_count(0)
    expect(page.get_by_role("banner")).to_be_visible()

    # Leaving the workbench restores the shell everywhere else.
    page.get_by_role("link", name="Alle Romane").click()
    expect(page.get_by_role("banner")).to_be_visible()
    expect(page.get_by_role("heading", name="Romane")).to_be_visible()
    assert_accessible(page)
