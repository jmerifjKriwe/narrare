"""Bounded prompts on the real stack: the cut and the skip are visible to the writer.

A chapter longer than the extraction bound is read partly, and its row says so; a
chapter the consistency check cannot fit is skipped by name. Both flows drive the
real UI, the real API and the real database — the provider stays the product's own
fake, the one permitted fake, at its own boundary.
"""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.kernel.testing.a11y import assert_accessible

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

LONG_BODY = "x" * 20_001


def _create_book(page: Page, title: str) -> None:
    """Create a novel the only way a user can, then open its workspace."""
    page.goto("http://127.0.0.1:3100/")
    page.get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill(title)
    page.get_by_role("button", name="Anlegen").click()
    page.get_by_role("link", name=title).click()
    expect(page.get_by_role("heading", name=title)).to_be_visible()


def _chapter(page: Page, body: str) -> None:
    """Create one chapter and type `body` into it, waiting for the save."""
    page.get_by_role("button", name="Neues Kapitel").click()
    editor = page.locator(".ProseMirror")
    expect(editor).to_be_visible()
    editor.click()
    page.keyboard.insert_text(body)
    # Extraction reads what the server has: wait for the save the editor reports.
    expect(page.get_by_text("Gespeichert")).to_be_visible()


def test_a_long_chapter_names_its_truncated_read(page: Page, stack: Stack) -> None:
    """20 001 characters: the extraction says it read only the first 20 000."""
    _create_book(page, "Die Bucht")
    _chapter(page, LONG_BODY)

    page.get_by_role("button", name="Wissen", exact=True).click()
    dock = page.get_by_role("complementary", name="Wissen")
    expect(dock).to_be_visible()
    dock.get_by_role("button", name="Dieses Kapitel durchsuchen").click()

    expect(
        dock.get_by_text("Nur die ersten 20.000 Zeichen wurden gelesen.", exact=True)
    ).to_be_visible(timeout=20_000)

    assert_accessible(page)


def test_a_long_chapter_is_skipped_by_name_in_the_check(page: Page, stack: Stack) -> None:
    """The check cannot read 20 001 characters and names the chapter instead."""
    _create_book(page, "Der Priel")
    _chapter(page, LONG_BODY)
    _chapter(page, "Mira ist 34 und bleibt es.")

    page.get_by_role("button", name="Wissen", exact=True).click()
    dock = page.get_by_role("complementary", name="Wissen")
    expect(dock).to_be_visible()
    dock.get_by_role("button", name="Ganzes Buch prüfen").click()

    expect(dock.get_by_text("Übersprungen, zu lang: Kapitel 1", exact=True)).to_be_visible(
        timeout=20_000
    )

    assert_accessible(page)
