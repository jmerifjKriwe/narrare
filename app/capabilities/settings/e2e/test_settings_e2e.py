"""A chosen language is remembered by the instance, not by the browser.

The browser is the one thing the test controls twice: the second context shares
no storage with the first, exactly like a different browser or a cleared cache.
If the choice lived in localStorage, that second window would fall back to the
browser's language — which is de-DE, so the failure is visible and not a guess.
"""

import itertools
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Browser, Page, expect

from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.stack import API_URL, WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

URL = f"{WEB_URL}/knowledge"
APPEARANCE = f"{WEB_URL}/settings/appearance"
THEME_PATCH = "/api/settings/theme"


def test_a_chosen_language_survives_a_fresh_browser(
    page: Page, stack: Stack, browser: Browser
) -> None:
    page.goto(URL)

    # Nobody has chosen: the browser's language (de-DE, pinned in conftest) wins.
    expect(page.get_by_role("heading", name="Wissen")).to_be_visible()
    switcher = page.get_by_role("banner").locator('select[name="locale"]')
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
        other.get_by_role("banner").locator('select[name="locale"]').select_option("auto")
        expect(other.get_by_role("heading", name="Wissen")).to_be_visible()
        expect(other.locator("html")).to_have_attribute("lang", "de")
    finally:
        other_context.close()

    assert_accessible(page)


def test_a_chosen_register_survives_a_reload(page: Page, stack: Stack) -> None:
    page.goto(f"{WEB_URL}/settings/language")
    expect(page.get_by_role("heading", name="Sprache")).to_be_visible()

    # The default is the familiar register, and the hint says so.
    formality = page.get_by_role("banner").locator('select[name="formality"]')
    expect(formality).to_have_value("informal")
    expect(page.get_by_text("Wie Narrare dich anspricht.")).to_be_visible()

    formality.select_option("formal")
    expect(page.get_by_text("Wie Narrare Sie anspricht.")).to_be_visible()

    # The register is a local choice; a reload reads it back before the paint.
    page.reload()
    expect(page.get_by_role("banner").locator('select[name="formality"]')).to_have_value("formal")
    expect(page.get_by_text("Wie Narrare Sie anspricht.")).to_be_visible()

    assert_accessible(page)


def test_skip_link_jumps_to_main_content(page: Page, stack: Stack) -> None:
    # A short window with books on the shelf, so the page really scrolls: the
    # shell is one viewport tall and #main owns the page scroll, so the rule
    # under test — a scroll container must be reachable by keyboard — is only
    # exercised while the content overflows (#638). The assertion below proves
    # that state instead of trusting the viewport; a taller shelf would
    # otherwise pass this test for the wrong reason.
    page.set_viewport_size({"width": 1280, "height": 320})
    for index in range(6):
        created = page.request.post(
            f"{API_URL}/api/writing/novels", data={"title": f"Regal {index}"}
        )
        assert created.ok, created.text()
    page.goto(f"{WEB_URL}/")
    expect(page.get_by_role("link", name="Regal 0")).to_be_visible()
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

    # The state the rule is about: the region scrolls, and it is in the tab
    # order. -1 held the skip link's landing and left the scroller unreachable
    # by keyboard; 0 is the stop the rule asks for.
    measured = page.evaluate(
        "() => { const main = document.getElementById('main');"
        " return main === null ? null : [main.scrollHeight, main.clientHeight]; }"
    )
    assert measured is not None and measured[0] > measured[1], (
        f"the page does not scroll, so the rule is not exercised: {measured}"
    )
    assert_accessible(page)

    expect(page.locator("#main")).to_have_attribute("tabindex", "0")


def test_the_frame_lists_rows_and_keeps_its_columns(page: Page, stack: Stack) -> None:
    """The settings frame's geometry: the cluster nav is a row list in its own
    200 px column, and the pages render beside it — never spilled into it."""
    page.goto(f"{WEB_URL}/settings")

    # The area's one cluster navigation — distinct from the rail's
    # Hauptnavigation by its name.
    nav = page.get_by_role("navigation", name="Einstellungen")
    links = nav.get_by_role("link")
    # The area's three clusters plus every registry row (prompts contributes
    # its page; a new cluster appears here with no edit to the layout).
    expect(links).to_have_count(4)

    # The nav is a column: 200 px wide, the rows stacked one under the next,
    # each the row's 28 px control height — not a run of shrink-wrapped
    # chips on one line.
    nav_box = nav.bounding_box()
    assert nav_box is not None
    assert nav_box["width"] == 200
    rows = [links.nth(index).bounding_box() for index in range(4)]
    boxes = [box for box in rows if box is not None]
    assert len(boxes) == 4
    for earlier, later in itertools.pairwise(boxes):
        assert earlier["y"] < later["y"]
    for box in boxes:
        assert box["width"] == 200  # a row fills its column
        assert box["height"] == 28  # the row's control height
    # A row is square: the surface radius belongs to panels, never rows.
    assert links.first.evaluate("el => getComputedStyle(el).borderRadius") == "0px"

    # The frame keeps its columns to itself: every hub door renders beside
    # the nav, at the content column's width — an unwrapped multi-root page
    # auto-places its fragment children into the grid, and from the second
    # section on they land in the nav's own cell (measured x=180 w=200),
    # which is the regression this pin exists to catch.
    for name in ("Sprache", "Darstellung", "Anbieter", "Prompts"):
        region_box = page.get_by_role("region", name=name).bounding_box()
        assert region_box is not None
        assert region_box["x"] >= nav_box["x"] + nav_box["width"]
        assert abs(region_box["width"] - 736) <= 1  # 1000 - 2*16 - 200 - 32

    assert_accessible(page)


def test_every_settings_page_names_itself_and_marks_its_cluster(page: Page, stack: Stack) -> None:
    """The tab names the page showing (WCAG 2.4.2) on every settings page,
    and the active cluster row says so with ``aria-current``."""
    page.goto(f"{WEB_URL}/settings")
    expect(page).to_have_title("Einstellungen — Narrare")

    # A sub-page owns its own name — the landing's, not the area's.
    page.goto(f"{WEB_URL}/settings/language")
    expect(page).to_have_title("Sprache — Narrare")
    expect(
        page.get_by_role("navigation", name="Einstellungen").get_by_role("link", name="Sprache")
    ).to_have_attribute("aria-current", "page")

    page.goto(f"{WEB_URL}/settings/provider")
    expect(page).to_have_title("Anbieter — Narrare")
    expect(
        page.get_by_role("navigation", name="Einstellungen").get_by_role("link", name="Anbieter")
    ).to_have_attribute("aria-current", "page")

    page.goto(APPEARANCE)
    expect(page).to_have_title("Darstellung — Narrare")
    expect(
        page.get_by_role("navigation", name="Einstellungen").get_by_role("link", name="Darstellung")
    ).to_have_attribute("aria-current", "page")

    assert_accessible(page)


def test_a_chosen_theme_survives_a_reload(page: Page, stack: Stack) -> None:
    """The reader's light is user data, not a browser preference: with the
    paint hint cleared, only the row can make the next reload wear it."""
    page.request.patch(f"{API_URL}{THEME_PATCH}", data={"theme": None})
    page.goto(APPEARANCE)
    expect(page.get_by_role("heading", name="Darstellung")).to_be_visible()

    # The write must land before the reload: an unload mid-request would
    # leave the row unset and the test would pass on the hint alone.
    with page.expect_response(
        lambda response: response.url.endswith(THEME_PATCH) and response.request.method == "PATCH"
    ):
        page.get_by_label("Farbschema").select_option("dark")
    page.evaluate("localStorage.removeItem('narrare.theme')")
    page.reload()
    expect(page.get_by_role("heading", name="Darstellung")).to_be_visible()
    assert page.evaluate("document.documentElement.dataset.theme") == "dark"
    dark = page.evaluate("getComputedStyle(document.body).backgroundColor")

    with page.expect_response(
        lambda response: response.url.endswith(THEME_PATCH) and response.request.method == "PATCH"
    ):
        page.get_by_label("Farbschema").select_option("light")
    page.evaluate("localStorage.removeItem('narrare.theme')")
    page.reload()
    expect(page.get_by_role("heading", name="Darstellung")).to_be_visible()
    assert page.evaluate("document.documentElement.dataset.theme") == "light"
    light = page.evaluate("getComputedStyle(document.body).backgroundColor")
    assert dark != light

    # Leave the row as the suite found it: the system case must decide from
    # the media query, not from this choice.
    page.request.patch(f"{API_URL}{THEME_PATCH}", data={"theme": None})


def test_an_unchosen_theme_follows_the_system(browser: Browser, stack: Stack) -> None:
    """No stored choice: `light-dark()` follows the OS live, both ways, and
    no attribute is written."""
    context = browser.new_context(color_scheme="light", locale="de-DE")
    try:
        page = context.new_page()
        page.request.patch(f"{API_URL}{THEME_PATCH}", data={"theme": None})
        page.goto(URL)
        assert page.evaluate("document.documentElement.dataset.theme ?? null") is None
        light = page.evaluate("getComputedStyle(document.body).backgroundColor")

        page.emulate_media(color_scheme="dark")
        page.wait_for_function(
            "(light) => getComputedStyle(document.body).backgroundColor !== light",
            arg=light,
        )
        assert page.evaluate("document.documentElement.dataset.theme ?? null") is None

        page.emulate_media(color_scheme="light")
        page.wait_for_function(
            "(light) => getComputedStyle(document.body).backgroundColor === light",
            arg=light,
        )
    finally:
        context.close()


def test_a_forced_theme_ignores_the_system(page: Page, stack: Stack) -> None:
    """A stored value wins over the OS, in both directions."""
    page.request.patch(f"{API_URL}{THEME_PATCH}", data={"theme": "light"})
    page.goto(APPEARANCE)
    expect(page.get_by_role("heading", name="Darstellung")).to_be_visible()
    light = page.evaluate("getComputedStyle(document.body).backgroundColor")

    page.emulate_media(color_scheme="dark")
    assert page.evaluate("document.documentElement.dataset.theme") == "light"
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") == light

    page.request.patch(f"{API_URL}{THEME_PATCH}", data={"theme": None})
