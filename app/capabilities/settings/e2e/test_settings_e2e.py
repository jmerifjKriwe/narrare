"""A chosen language is remembered by the instance, not by the browser.

The browser is the one thing the test controls twice: the second context shares
no storage with the first, exactly like a different browser or a cleared cache.
If the choice lived in localStorage, that second window would fall back to the
browser's language — which is de-DE, so the failure is visible and not a guess.
"""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Browser, Page, expect

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

URL = "http://127.0.0.1:3100/knowledge"


def test_a_chosen_language_survives_a_fresh_browser(
    page: Page, stack: Stack, browser: Browser
) -> None:
    page.goto(URL)

    # Nobody has chosen: the browser's language (de-DE, pinned in conftest) wins.
    expect(page.get_by_role("heading", name="Wissen")).to_be_visible()
    switcher = page.get_by_role("combobox")
    expect(switcher).to_have_value("auto")
    expect(page.locator("html")).to_have_attribute("lang", "de")

    switcher.select_option("en")
    expect(page.get_by_role("heading", name="Knowledge")).to_be_visible()
    # The document language follows the rendered text: screen readers and
    # hyphenation read the language of the page, not the browser's preference.
    expect(page.locator("html")).to_have_attribute("lang", "en")

    # A second browser: no cookie, no localStorage, nothing shared but the API.
    other_context = browser.new_context(locale="de-DE")
    try:
        other = other_context.new_page()
        other.goto(URL)

        # de-DE speaks, English is shown: the stored row decided.
        expect(other.get_by_role("heading", name="Knowledge")).to_be_visible()
        expect(other.locator("html")).to_have_attribute("lang", "en")

        # Back to automatic, and the browser decides again.
        other.get_by_role("combobox").select_option("auto")
        expect(other.get_by_role("heading", name="Wissen")).to_be_visible()
        expect(other.locator("html")).to_have_attribute("lang", "de")
    finally:
        other_context.close()
