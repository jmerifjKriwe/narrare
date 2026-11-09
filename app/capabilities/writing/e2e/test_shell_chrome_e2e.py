"""The shell's chrome answers the surface it stands on.

Two pins P12's rounds left behind. R29 splits the icon rail's breakpoint by
surface: on the workspace the prose floor owns 1024-1279, so the rail waits
for 1280 there (the dock child included — the workspace parent is in its
match chain, the one leg where the route, not the width alone, decides);
on every other route the rail is chrome like the bar and shows from 1024 —
all four states pinned plus the dock child, hidden-but-mounted. And the
brand serif ships in both voices the prose surface speaks: the 400 the
editor reads in, and the 600 the chapter heading wears (R33) — asserted
through the FontFaceSet, so a face that silently fails to ship fails here
instead of rendering as the synthesised stand-in a 400 would become.
"""

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Browser, Page, expect

from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.stack import WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

WEB = WEB_URL
PROSE = ".ProseMirror"
# The global rail announces itself to every reader; the label is what a
# test can trust. (The workbench's chapter aside has its own file.)
ICON_RAIL = 'nav[aria-label="Hauptnavigation"]'


def _create_workspace(page: Page, title: str) -> str:
    """A book with one chapter, made the only way a user can; leaves the
    browser on the workbench with the editor rendered and returns the
    workspace's bare URL (no search), so a test can walk to a dock child."""
    page.goto(f"{WEB}/")
    page.get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill(title)
    page.get_by_role("button", name="Anlegen").click()
    page.get_by_role("link", name=title).click()
    expect(page.get_by_role("heading", name=title)).to_be_visible()
    page.get_by_role("button", name="Neues Kapitel").click()
    expect(page.locator(PROSE)).to_be_visible()
    return page.url.split("?")[0]


def test_the_editor_ships_both_garamond_faces(page: Page, stack: Stack) -> None:
    """The 400 the prose reads in and the 600 the heading wears are both
    registered and loaded once the editor renders — not synthesised."""
    _create_workspace(page, "Die Stimmen des Meers")
    verdict: object = page.evaluate(
        """async () => {
          await document.fonts.ready;
          // load() forces the lazy faces the queries name: font-display: swap
          // leaves an unused face unloaded, and check() reads load state.
          await document.fonts.load('18px "EB Garamond"');
          await document.fonts.load('600 18px "EB Garamond"');
          // Chromium's check() answers a query whose style matches no
          // registered face vacuously true — for a 600 request it falls
          // back to the 400 it would synthesise bold from, and even for a
          // family that ships nothing at all. So the 600 leg counts the
          // registered, loaded 600 face before trusting check()'s word;
          // without one this is false whatever check() answers.
          const faces = [...document.fonts].filter(
            (f) => f.family.replaceAll('"', '') === 'EB Garamond',
          );
          const shipped = faces.some(
            (f) => f.weight === '600' && f.status === 'loaded',
          );
          // A declared 600 whose src quietly points at the 400 file would
          // pass everything above — the descriptor, not the bytes, is what
          // the FontFaceSet reads. The two files must be two faces: an
          // own length, or failing that at least one byte of their own
          // (same-length distinct files differ somewhere; the same file
          // differs nowhere).
          const [regular, semibold] = await Promise.all(
            ['/fonts/eb-garamond-latin.woff2', '/fonts/eb-garamond-latin-600.woff2'].map(
              (url) => fetch(url).then((r) => r.arrayBuffer()),
            ),
          );
          const a = new Uint8Array(regular);
          const b = new Uint8Array(semibold);
          const twoFiles =
            regular.byteLength !== semibold.byteLength ||
            a.some((byte, i) => byte !== b[i]);
          return (
            twoFiles &&
            shipped &&
            document.fonts.check('18px "EB Garamond"') &&
            document.fonts.check('600 18px "EB Garamond"')
          );
        }""",
    )
    assert verdict is True, "the editor's two Garamond faces are not both loaded"


@pytest.mark.parametrize("width", [1024, 1280])
def test_the_icon_rail_answers_the_surface(page: Page, stack: Stack, width: int) -> None:
    """R29, all four states pinned: at 1024 the rail shows on the shelf and
    stays off the workspace (the prose floor owns that band there); at 1280
    it shows on both."""
    title = f"Der lange Weg {width}"
    page.set_viewport_size({"width": width, "height": 720})
    url = _create_workspace(page, title)

    # The workspace face: chrome only from 1280 here. The count pin keeps
    # the rail mounted — hidden, not detached — so `hidden` stays the
    # mechanism and a conditional unmount cannot impersonate it.
    if width < 1280:
        expect(page.locator(ICON_RAIL)).to_have_count(1)
        expect(page.locator(ICON_RAIL)).to_be_hidden()
    else:
        expect(page.locator(ICON_RAIL)).to_be_visible()

    # The dock child, below 1280 only: the workspace parent is in the match
    # chain there — the only leg where that mechanism, not the width alone,
    # decides the answer. The rail must stay hidden.
    if width < 1280:
        page.goto(f"{url}/knowledge")
        expect(page.locator('aside[aria-label="Wissen"]')).to_be_visible()
        expect(page.locator(ICON_RAIL)).to_have_count(1)
        expect(page.locator(ICON_RAIL)).to_be_hidden()

    # Every other surface: the rail shows from 1024, like the bar.
    page.goto(f"{WEB}/")
    expect(page.get_by_role("link", name=title)).to_be_visible()
    expect(page.locator(ICON_RAIL)).to_be_visible()


def test_the_unknown_url_names_itself_and_reads_the_scale(page: Page, stack: Stack) -> None:
    """R49: the 404 joins the system — it names itself to the tab and the
    bar (usePageTitle), and its heading walks the title step (20), not a
    hand-picked size."""
    page.goto(f"{WEB}/gibt-es-nicht")
    expect(page).to_have_title("Diese Seite existiert nicht. — Narrare")
    expect(page.get_by_role("heading", name="Diese Seite existiert nicht.")).to_be_visible()
    assert (
        page.evaluate("getComputedStyle(document.querySelector('h1.text-title')).fontSize")
        == "20px"
    )
    # The surface stands alone (in place of the Shell) and still answers
    # the accessibility floor.
    assert_accessible(page)


def test_the_workspace_shows_one_filled_primary_with_the_chat_dock_open(
    page: Page, stack: Stack
) -> None:
    """L1 on the busiest screen: with the chat dock open, the workspace
    answers exactly one filled primary — the editor's Weiterschreiben. The
    dock's ask button reads as a secondary (R46): its paint carries no
    primary fill. The class is the contract's handle — the unit matrix pins
    that `bg-primary` means the fill — so the screen pin counts the class,
    and names the one survivor."""
    _create_workspace(page, "Die eine Primärfarbe")

    page.get_by_role("button", name="Chat", exact=True).click()
    dock = page.get_by_role("complementary", name="Chat")
    expect(dock).to_be_visible()

    ask = dock.get_by_role("button", name="Fragen")
    expect(ask).to_be_visible()
    expect(ask).not_to_have_class(re.compile(r"bg-primary"))

    primaries = page.locator("button.bg-primary")
    expect(primaries).to_have_count(1)
    expect(primaries).to_contain_text("Weiterschreiben")


def test_the_palette_key_opens_it_by_pointer(page: Page, stack: Stack) -> None:
    """The bar's keycap is a door, not a decoration: a pointer user reaches
    the palette without knowing the shortcut."""
    page.goto(f"{WEB}/")
    page.get_by_role("button", name="Befehlspalette öffnen").click()
    expect(page.get_by_role("dialog", name="Befehlspalette")).to_be_visible()


def test_the_rail_names_itself_on_hover(page: Page, stack: Stack) -> None:
    """The icon rail opens over the page on hover: the names were always in
    the DOM, and the collapsed rail clips them at 48 px."""
    page.goto(f"{WEB}/")
    rail = page.locator(ICON_RAIL)
    label = rail.get_by_text("Wissen")
    expect(rail).to_have_css("width", "48px")
    expect(label).to_have_css("opacity", "0")
    rail.hover()
    expect(rail).to_have_css("width", "168px")
    expect(label).to_have_css("opacity", "1")


@pytest.mark.parametrize("width", [1024, 1280])
def test_the_expanded_rail_moves_no_page_pixels(page: Page, stack: Stack, width: int) -> None:
    """The expansion is an overlay in a fixed slot: the page axis stays put
    at both breakpoints that show the rail."""
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(f"{WEB}/")
    before = page.locator("main").bounding_box()
    page.locator(ICON_RAIL).hover()
    assert page.locator("main").bounding_box() == before


def test_the_rail_tells_the_four_areas_apart(page: Page, stack: Stack) -> None:
    """Each entry's icon wrapper carries its area's token; four areas, four
    colours, none of them the link's muted ink."""
    page.goto(f"{WEB}/")
    # The shell paints after its settings query answers: wait for it, or the
    # lookup races an empty document.
    expect(page.locator(ICON_RAIL)).to_be_visible()
    colours = page.evaluate(
        """() => ["Startseite", "Wissen", "Chat", "Einstellungen"].map((name) => {
          const link = document.querySelector(`nav a[aria-label="${name}"]`);
          return getComputedStyle(link.querySelector("span")).color;
        })"""
    )
    assert len(set(colours)) == 4, colours


def test_tabbing_into_the_rail_opens_it(page: Page, stack: Stack) -> None:
    """A keyboard user gets the names too: focus-within opens the rail."""
    page.goto(f"{WEB}/")
    for _ in range(20):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement?.closest('nav') !== null"):
            break
    else:
        raise AssertionError("the tab order never reached the rail")
    expect(page.locator(ICON_RAIL)).to_have_css("width", "168px")


def test_a_touch_pointer_gets_permanent_labels(browser: Browser, stack: Stack) -> None:
    """No hover on a coarse pointer, so the names stand open there."""
    # The suite's `de-DE` lives in `browser_context_args`
    # (app/capabilities/conftest.py) and reaches only the `page` fixture. A
    # hand-made context inherits the host's locale — German here, en-US on the
    # runner — and with the seeded user holding no locale the app follows it:
    # the rail would answer "Main navigation" and the German selector below
    # would miss. Repeat the pin, as the settings suite does.
    context = browser.new_context(
        has_touch=True,
        viewport={"width": 1280, "height": 900},
        locale="de-DE",
    )
    try:
        page = context.new_page()
        page.goto(f"{WEB}/")
        expect(page.locator(ICON_RAIL)).to_have_css("width", "168px")
        expect(page.locator(ICON_RAIL).get_by_text("Wissen")).to_have_css("opacity", "1")
    finally:
        context.close()
