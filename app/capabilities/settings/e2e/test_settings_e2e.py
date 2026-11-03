"""A chosen language is remembered by the instance, not by the browser.

The browser is the one thing the test controls twice: the second context shares
no storage with the first, exactly like a different browser or a cleared cache.
If the choice lived in localStorage, that second window would fall back to the
browser's language — which is de-DE, so the failure is visible and not a guess.
"""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Browser, Page, expect

from app.kernel.testing.a11y import assert_accessible

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

    assert_accessible(page)


def test_skip_link_jumps_to_main_content(page: Page, stack: Stack) -> None:
    page.goto("http://127.0.0.1:3100/")
    # The shell paints only after the settings query answers — the locale
    # gate — so the Tab below must wait for the bar to exist.
    expect(page.locator("header")).to_be_visible()
    # Keyboard, not locator presses: Locator.press focuses its target first,
    # and body is not focusable — the surviving skip-link focus is only a
    # no-op side effect this test must not lean on. The keyboard path sends
    # the keys to whatever is actually focused, which is the contract the
    # skip link lives by.
    page.keyboard.press("Tab")  # first Tab reaches the skip link
    expect(page.get_by_role("link", name="Zum Inhalt springen")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("#main")).to_be_focused()

    assert_accessible(page)


def test_the_frame_lists_rows_and_keeps_its_columns(page: Page, stack: Stack) -> None:
    """The settings frame's geometry: the cluster nav is a row list in its own
    200 px column, and the pages render beside it — never spilled into it."""
    page.goto("http://127.0.0.1:3100/settings")

    # The area's one cluster navigation — distinct from the rail's
    # Hauptnavigation by its name.
    nav = page.get_by_role("navigation", name="Einstellungen")
    links = nav.get_by_role("link")
    # The area's two clusters plus every registry row (prompts contributes
    # its page; a new cluster appears here with no edit to the layout).
    expect(links).to_have_count(3)

    # The nav is a column: 200 px wide, the rows stacked one under the next,
    # each the row's 28 px control height — not a run of shrink-wrapped
    # chips on one line.
    nav_box = nav.bounding_box()
    assert nav_box is not None
    assert nav_box["width"] == 200
    first = links.nth(0).bounding_box()
    second = links.nth(1).bounding_box()
    third = links.nth(2).bounding_box()
    assert first is not None and second is not None and third is not None
    assert first["y"] < second["y"] < third["y"]
    for box in (first, second, third):
        assert box["width"] == 200  # a row fills its column
        assert box["height"] == 28  # the row's control height
    # A row is square: the surface radius belongs to panels, never rows.
    assert links.first.evaluate("el => getComputedStyle(el).borderRadius") == "0px"

    # The frame keeps its columns to itself: every hub door renders beside
    # the nav, at the content column's width — an unwrapped multi-root page
    # auto-places its fragment children into the grid, and from the second
    # section on they land in the nav's own cell (measured x=180 w=200),
    # which is the regression this pin exists to catch.
    for name in ("Sprache", "Anbieter", "Prompts"):
        region_box = page.get_by_role("region", name=name).bounding_box()
        assert region_box is not None
        assert region_box["x"] >= nav_box["x"] + nav_box["width"]
        assert abs(region_box["width"] - 736) <= 1  # 1000 - 2*16 - 200 - 32

    assert_accessible(page)


def test_every_settings_page_names_itself_and_marks_its_cluster(page: Page, stack: Stack) -> None:
    """The tab names the page showing (WCAG 2.4.2) on every settings page,
    and the active cluster row says so with ``aria-current``."""
    page.goto("http://127.0.0.1:3100/settings")
    expect(page).to_have_title("Einstellungen — Narrare")

    # A sub-page owns its own name — the landing's, not the area's.
    page.goto("http://127.0.0.1:3100/settings/language")
    expect(page).to_have_title("Sprache — Narrare")
    expect(
        page.get_by_role("navigation", name="Einstellungen").get_by_role("link", name="Sprache")
    ).to_have_attribute("aria-current", "page")

    page.goto("http://127.0.0.1:3100/settings/provider")
    expect(page).to_have_title("Anbieter — Narrare")
    expect(
        page.get_by_role("navigation", name="Einstellungen").get_by_role("link", name="Anbieter")
    ).to_have_attribute("aria-current", "page")

    assert_accessible(page)
