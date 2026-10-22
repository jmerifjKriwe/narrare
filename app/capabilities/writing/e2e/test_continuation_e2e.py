"""Click once: the provider streams into the editor and the text survives reload."""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.kernel.testing.a11y import assert_accessible

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]


def test_the_continuation_arrives_in_the_editor_and_is_saved(page: Page, stack: Stack) -> None:
    page.goto("http://127.0.0.1:3100/")
    page.get_by_label("Titel").fill("Der Nebel")
    page.get_by_role("button", name="Anlegen").click()
    page.get_by_role("link", name="Der Nebel").click()
    page.get_by_role("button", name="Neues Kapitel").click()

    editor = page.locator(".ProseMirror")
    editor.click()
    page.keyboard.type("Der Nebel kam von See.")
    expect(page.get_by_text("Gespeichert")).to_be_visible()

    page.get_by_role("button", name="Weiterschreiben").click()
    expect(editor).to_contain_text("Der Nebel hob sich ")
    expect(editor).to_contain_text("über die Straße.")

    # The stream ends, then the 800 ms debounce writes. The indicator cannot
    # prove this save: it already shows "Gespeichert" from the typing, and it
    # clears on the first delta. The reload is the proof that it persisted.
    page.wait_for_timeout(1500)
    page.reload()
    expect(page.locator(".ProseMirror")).to_contain_text("über die Straße.")

    assert_accessible(page)
