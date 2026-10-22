"""A novel typed into the browser must reach Postgres and survive a reload."""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.kernel.testing.a11y import assert_accessible

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]


def test_novel_created_in_browser_survives_reload(page: Page, stack: Stack) -> None:
    page.goto("http://127.0.0.1:3100/")
    page.get_by_label("Titel").fill("Der Nebel")
    page.get_by_role("button", name="Anlegen").click()
    expect(page.get_by_text("Der Nebel")).to_be_visible()

    page.reload()
    expect(page.get_by_text("Der Nebel")).to_be_visible()

    assert_accessible(page)


def test_landing_page_reports_an_unreachable_backend(page: Page, stack: Stack) -> None:
    """A local service the user has not started must be named, not shown as empty."""
    page.goto("http://127.0.0.1:3100/")
    expect(page.get_by_label("Titel")).to_be_visible()

    stack.stop_api()
    try:
        page.reload()
        # The alert is the page's own error message; nothing else claims the role.
        expect(page.get_by_role("alert").filter(has_text="nicht geladen")).to_be_visible()
    finally:
        stack.start_api()

    # The same page recovers once the service answers again.
    page.reload()
    expect(page.get_by_label("Titel")).to_be_visible()

    assert_accessible(page)
