"""Autosave tells the truth about the answer it got.

A refused write is named beside the text and never worn as "saved"; the body
it carried survives in memory, and the next keystroke retries it against the
recovered service — proven on the real stack, outage included.
"""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

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
    _create_book(page, "Die Bucht")
    page.get_by_role("button", name="Neues Kapitel").click()
    page.locator(".ProseMirror").click()

    stack.stop_api()
    page.keyboard.type("Der Satz, den niemand speichert.")
    expect(page.get_by_text("Nicht gespeichert", exact=True)).to_be_visible(timeout=10_000)
    expect(page.get_by_text("Gespeichert", exact=True)).to_have_count(0)

    stack.start_api()
    page.keyboard.type(" Und noch ein Wort.")
    expect(page.get_by_text("Gespeichert", exact=True)).to_be_visible(timeout=10_000)

    page.reload()
    expect(page.locator(".ProseMirror")).to_contain_text("Und noch ein Wort.")

    assert_accessible(page)
