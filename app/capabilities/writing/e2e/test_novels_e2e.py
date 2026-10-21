"""A novel typed into the browser must reach Postgres and survive a reload."""

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]


def test_novel_created_in_browser_survives_reload(page: Page, stack: None) -> None:
    page.goto("http://127.0.0.1:3100/")
    page.get_by_label("Titel").fill("Der Nebel")
    page.get_by_role("button", name="Anlegen").click()
    expect(page.get_by_text("Der Nebel")).to_be_visible()

    page.reload()
    expect(page.get_by_text("Der Nebel")).to_be_visible()
