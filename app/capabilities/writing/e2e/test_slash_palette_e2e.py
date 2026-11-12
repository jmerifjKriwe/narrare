"""The slash door into the command palette.

`/` in an empty editor paragraph opens the palette prefilled with `/` — the
action list, not the empty truth — and Escape closes it without leaving the
slash in the prose. Real stack throughout: browser, API, Postgres.
"""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

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
    page.locator("header").get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill(title)
    page.get_by_role("button", name="Anlegen", exact=True).click()
    page.get_by_role("link", name=title).click()
    expect(page.get_by_role("heading", name=title)).to_be_visible()


def test_slash_opens_the_palette_and_escape_leaves_no_slash(page: Page, stack: Stack) -> None:
    """`/` with the caret in an empty paragraph is the palette's door, not text.

    The field opens prefilled with `/` and still lists the actions; Escape
    closes the palette and the prose holds no stray slash.
    """
    _create_book(page, "Der Schrägstrich")
    new_chapter(page)
    editor = page.locator(".ProseMirror")
    editor.click()
    # The new chapter's body is empty: the caret sits in an empty paragraph.
    page.keyboard.press("/")

    dialog = page.get_by_role("dialog", name="Befehlspalette")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role("textbox")).to_have_value("/")
    # The visible result is the action list, not the empty truth.
    expect(dialog.get_by_role("button", name="Neues Kapitel")).to_be_visible()

    page.keyboard.press("Escape")
    expect(dialog).to_have_count(0)
    # The slash opened the palette; none of it may remain in the prose.
    assert (editor.text_content() or "") == ""
