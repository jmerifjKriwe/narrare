"""The viewport floor: the page fits every width, and below 1024 panels cover.

Four widths (360, 768, 1024, 1280) over the shell's five faces — the shelf,
the workbench with its rail open, the workbench with the dock open, the
settings hub, the prompts page. Every visit answers two questions: does the
document fit its viewport, and where an editor is on screen, does the prose
column keep its 320 px floor. Below 1024 the rail and the dock are asked the
overlay question too: cover the editor, never move it — a squeeze of one
pixel is a failure — and never paint over the workbench's own controls: the
drawers start below the toolbar band, pinned by a hit-test on the focus
toggle and, from 768 up, by opening the dock with its real tab.

A violation on one face says nothing about the others, so the sweep collects
instead of stopping: one run reports every face every width broke, and the
recorded red is the defect's whole shape, not its first symptom.
"""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.kernel.testing.viewport import assert_overlay, assert_page_fits

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

WEB = "http://127.0.0.1:3100"
PROSE = ".ProseMirror"
# The workbench's editor column: the min-w-0 flex item the panels must never
# move. The overlay delta is measured here, not on the prose element — the
# prose caps at 34rem, so in the ~900 to 1023 band a squeezing panel would
# shrink only the empty remainder and the capped box would hide it.
EDITOR = "section.min-w-0"
# The rail announces itself by its heading, the dock by its title; the labels
# are what a screen reader reads, so they are the selectors a test can trust.
RAIL = 'aside[aria-label="Kapitel"]'
DOCK = 'aside[aria-label="Wissen"]'
FOCUS_TOGGLE = "Ablenkungen ausblenden"
DOCK_TAB = "Wissen"
WIDTHS = [360, 768, 1024, 1280]
# The breakpoint the workbench's own classes use: below it the panels are
# overlays, at and above it they are the desktop columns the older E2Es pin.
OVERLAY_BELOW = 1024


def _create_workspace(page: Page, title: str) -> None:
    """A book with one chapter, made the only way a user can.

    Created at the desktop size — the sweep measures pages at a width, not
    the new-book dialog — then left for the sweep to revisit at each face.
    """
    page.set_viewport_size({"width": 1280, "height": 720})
    page.goto(f"{WEB}/")
    page.get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill(title)
    page.get_by_role("button", name="Anlegen").click()
    page.get_by_role("link", name=title).click()
    expect(page.get_by_role("heading", name=title)).to_be_visible()
    page.get_by_role("button", name="Neues Kapitel").click()
    expect(page.locator(PROSE)).to_be_visible()


def _probe(collected: list[str], label: str, measure) -> None:
    """Collect one measurement's failure under its face's name, or pass."""
    try:
        measure()
    except pytest.fail.Exception as failure:
        collected.append(f"  [{label}] {failure}")


def _control_clears_the_drawer(page: Page, label: str) -> None:
    """The control's centre must hit-test back to itself.

    Playwright's visibility is not occlusion-aware; elementFromPoint is.
    A drawer painting over the toolbar answers with its own content, and
    this fails with that verdict.
    """
    box = page.get_by_role("button", name=label).bounding_box()
    if box is None:
        pytest.fail(f"the {label!r} control has no box to hit-test")
    verdict: object = page.evaluate(
        """([x, y, label]) => {
          const hit = document.elementFromPoint(x, y);
          const button = hit && hit.closest("button");
          return button && button.textContent.trim() === label
            ? "clear"
            : "covered";
        }""",
        [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, label],
    )
    if verdict != "clear":
        pytest.fail(f"the {label!r} control is painted over: hit-test says {verdict!r}")


def _pin_columns(page: Page) -> None:
    """At and above the breakpoint the rail is a column, not a drawer: its
    right edge ends where the editor section begins. A drift from ``max-lg:``
    to ``max-xl:`` would drawer-ize 1024 too — this is what catches it."""
    rail = page.locator(RAIL).bounding_box()
    editor = page.locator(EDITOR).bounding_box()
    if rail is None or editor is None:
        pytest.fail("the rail or the editor section has no box")
    if rail["x"] + rail["width"] > editor["x"]:
        pytest.fail(
            f"the rail is not a column: right edge "
            f"{rail['x'] + rail['width']}px runs past the editor's left "
            f"{editor['x']}px"
        )


def _pin_drawer_scrolls(page: Page) -> None:
    """The rail drawer must contain its own list: a long chapter list scrolls
    inside the drawer's background, never spills past it onto the page."""
    drawer = page.locator(RAIL)
    slack: object = drawer.evaluate("el => el.scrollHeight - el.clientHeight")
    if not isinstance(slack, (int, float)) or slack <= 0:
        pytest.fail(f"the rail drawer does not scroll: slack {slack}")
    drawer.evaluate("el => { el.scrollTop = el.scrollHeight }")
    drawer_box = drawer.bounding_box()
    last = drawer.get_by_role("button", name="Kapitel 8", exact=True)
    last_box = last.bounding_box()
    if drawer_box is None or last_box is None:
        pytest.fail("the drawer or its last chapter has no box")
    if last_box["y"] + last_box["height"] > drawer_box["y"] + drawer_box["height"] + 1:
        pytest.fail(
            f"the chapter list spills out of the drawer: last chapter ends at "
            f"{last_box['y'] + last_box['height']}px, drawer at "
            f"{drawer_box['y'] + drawer_box['height']}px"
        )
    # The reachability half: Playwright refuses a click it cannot land.
    last.click()


@pytest.mark.parametrize("width", WIDTHS)
def test_the_pages_fit_and_the_panels_cover(page: Page, stack: Stack, width: int) -> None:
    title = f"Der schmale Raum {width}"
    _create_workspace(page, title)
    page.set_viewport_size({"width": width, "height": 720})
    novel_url = page.url.split("?")[0]
    # The module's database is shared, so every width owns a book no other uses.
    failures: list[str] = []

    # The shelf: no editor on screen — the fit alone.
    page.goto(f"{WEB}/")
    expect(page.get_by_role("link", name=title)).to_be_visible()
    _probe(failures, f"{width}px /", lambda: assert_page_fits(page))

    # The workbench, rail open (the default): the prose floor where an
    # editor is on screen; below 1024 the rail must cover the editor —
    # not the workbench's own controls.
    page.goto(novel_url)
    expect(page.locator(PROSE)).to_be_visible()
    expect(page.locator(RAIL)).to_be_visible()
    _probe(
        failures,
        f"{width}px /novels rail open",
        lambda: assert_page_fits(page, prose_selector=PROSE),
    )
    if width < OVERLAY_BELOW:
        _probe(
            failures,
            f"{width}px /novels rail overlay",
            lambda: assert_overlay(page, editor_selector=EDITOR, panel_selector=RAIL),
        )
        _probe(
            failures,
            f"{width}px toolbar clears the rail",
            lambda: _control_clears_the_drawer(page, FOCUS_TOGGLE),
        )
    else:
        _probe(failures, f"{width}px columns", lambda: _pin_columns(page))

    # The dock open on top of the still-open rail — the worst case a narrow
    # window must survive. From 768 up the dock's own tab opens it: the rail
    # drawer starts below the toolbar band, and the click is Playwright's
    # occlusion proof. At 360 the toolbar wraps and its second line sits
    # under the drawers whatever the anchor does, so the visit arrives the
    # way a deep link does — at the dock's own address, which is the dock's
    # whole state.
    if width == 360:
        page.goto(f"{novel_url}/wissen")
    else:
        page.get_by_role("button", name=DOCK_TAB, exact=True).click()
    expect(page.locator(DOCK)).to_be_visible()
    _probe(
        failures,
        f"{width}px /novels dock open",
        lambda: assert_page_fits(page, prose_selector=PROSE),
    )
    if width < OVERLAY_BELOW:
        _probe(
            failures,
            f"{width}px /novels dock overlay",
            lambda: assert_overlay(page, editor_selector=EDITOR, panel_selector=DOCK),
        )

    # At 360 only: a tall fixture — seven more chapters, the only way a user
    # makes them — to pin the drawer containing its own list. The dock is
    # open when this face ends, and its drawer covers the rail's own button,
    # so the bare workbench address (no dock child route) comes first.
    if width == 360:
        page.goto(novel_url)
        expect(page.locator(RAIL)).to_be_visible()
        for _ in range(7):
            page.get_by_role("button", name="Neues Kapitel").click()
        expect(page.get_by_role("button", name="Kapitel 8", exact=True)).to_be_visible()
        _probe(failures, "360px rail drawer scrolls", lambda: _pin_drawer_scrolls(page))

    # The settings hub and the prompts page: no editor on either — the fit alone.
    page.goto(f"{WEB}/settings")
    expect(page.get_by_role("heading", name="Einstellungen")).to_be_visible()
    _probe(failures, f"{width}px /settings", lambda: assert_page_fits(page))

    page.goto(f"{WEB}/settings/prompts")
    expect(page.get_by_role("heading", name="Prompts")).to_be_visible()
    _probe(failures, f"{width}px /settings/prompts", lambda: assert_page_fits(page))

    assert not failures, "the viewport floor failed:\n" + "\n".join(failures)
