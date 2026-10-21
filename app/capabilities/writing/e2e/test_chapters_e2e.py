"""Text typed into the editor must be saved without a button and survive a reload."""

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]


def test_typed_chapter_body_survives_reload(page: Page, stack: None) -> None:
    page.goto("http://127.0.0.1:3100/")
    page.get_by_label("Titel").fill("Der Nebel")
    page.get_by_role("button", name="Anlegen").click()

    page.get_by_role("link", name="Der Nebel").click()
    expect(page.get_by_role("heading", name="Der Nebel")).to_be_visible()

    page.get_by_role("button", name="Neues Kapitel").click()
    editor = page.locator(".ProseMirror")
    editor.click()
    page.keyboard.type("Der Nebel kam von See.")

    # No save button: the indicator is the only proof the debounce fired.
    expect(page.get_by_text("Gespeichert")).to_be_visible()

    page.reload()
    expect(page.locator(".ProseMirror")).to_contain_text("Der Nebel kam von See.")
