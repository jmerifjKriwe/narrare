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

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

WEB = "http://127.0.0.1:3100"
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
          // own length and at least one byte of their own.
          const [regular, semibold] = await Promise.all(
            ['/fonts/eb-garamond-latin.woff2', '/fonts/eb-garamond-latin-600.woff2'].map(
              (url) => fetch(url).then((r) => r.arrayBuffer()),
            ),
          );
          const a = new Uint8Array(regular);
          const b = new Uint8Array(semibold);
          const twoFiles =
            regular.byteLength !== semibold.byteLength &&
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
        page.goto(f"{url}/wissen")
        expect(page.locator('aside[aria-label="Wissen"]')).to_be_visible()
        expect(page.locator(ICON_RAIL)).to_have_count(1)
        expect(page.locator(ICON_RAIL)).to_be_hidden()

    # Every other surface: the rail shows from 1024, like the bar.
    page.goto(f"{WEB}/")
    expect(page.get_by_role("link", name=title)).to_be_visible()
    expect(page.locator(ICON_RAIL)).to_be_visible()
