"""The mechanical viewport floor under every E2E flow: the page fits, panels cover.

Two assertions, the ones a narrow window fails first. ``assert_page_fits`` is
the honest whole-page measure — the document's ``scrollWidth`` against the
viewport's width, not a screenshot's — and, where an editor is on screen, the
prose column's **content box** (its bounding rect minus its own computed
horizontal paddings) against the 320 px a sentence needs. ``assert_overlay``
is the narrow-window panel contract: a panel floating over the editor must
lie at least half onto it, and the editor's width must not move by so much as
a pixel when the panel arrives — a panel that squeezes instead of covers or
merely clips an edge fails here, at the delta, not by eye.

Like the a11y floor beside it, the helper is deliberately unable to pass
without having measured: a missing viewport, a selector that matches nothing
and an invisible editor are all failures — a check that cannot fail protects
nothing.
"""

from typing import TYPE_CHECKING, cast

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page

# The prose floor: the narrowest column long-form text stays readable in.
# The workbench's own padding (px-4, twice) is what yields it on a 360 px
# phone — the page spends 32 px on margins and keeps 328 px for the words.
MIN_PROSE_WIDTH = 320

# Both halves of the content-box definition, read in the browser at the same
# moment: the border-box rect and the computed horizontal paddings. One
# evaluate instead of two so the two numbers cannot disagree about layout.
_MEASURE_CONTENT_BOX = r"""
(selector) => {
  const element = document.querySelector(selector);
  if (element === null) return null;
  const rect = element.getBoundingClientRect();
  const style = getComputedStyle(element);
  return {
    width: rect.width,
    padding: parseFloat(style.paddingLeft) + parseFloat(style.paddingRight),
  };
}
"""


def assert_page_fits(page: Page, *, prose_selector: str | None = None) -> None:
    """Fail unless ``page`` fits its viewport, its prose column at least 320 px.

    The fit is ``documentElement.scrollWidth`` — everything laid out, overlays
    included — against the viewport's width. With a ``prose_selector`` the
    content box (bounding rect minus computed horizontal paddings) must also
    clear :data:`MIN_PROSE_WIDTH`; the editor's own padding is what a narrow
    window spends on margins before the words lose their floor.
    """
    viewport = page.viewport_size
    if viewport is None:
        pytest.fail(f"the page has no viewport to fit: {page.url}")
    scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
    if scroll_width > viewport["width"]:
        pytest.fail(
            f"the page overflows its viewport on {page.url}: "
            f"scrollWidth {scroll_width} > {viewport['width']}px"
        )
    if prose_selector is None:
        return
    measured: object = page.evaluate(_MEASURE_CONTENT_BOX, prose_selector)
    if not isinstance(measured, dict):
        pytest.fail(f"the prose selector matched nothing on {page.url}: {prose_selector}")
    verdict = cast("dict[str, object]", measured)
    box, padding = verdict.get("width"), verdict.get("padding")
    if not isinstance(box, (int, float)) or not isinstance(padding, (int, float)):
        pytest.fail(f"the prose measurement came back malformed on {page.url}: {measured!r}")
    content_box = float(box) - float(padding)
    if content_box < MIN_PROSE_WIDTH:
        pytest.fail(
            f"the prose column is starved on {page.url}: content box "
            f"{content_box}px < {MIN_PROSE_WIDTH}px (box {box}px, "
            f"padding {padding}px)"
        )


def assert_overlay(page: Page, *, editor_selector: str, panel_selector: str) -> None:
    """Fail unless ``panel_selector`` lies onto ``editor_selector`` without moving it.

    The width comparison is the honest one: the panel is lifted out of the
    layout in place (``display: none``, then restored — no navigation, no
    state), the editor measured closed and open, and the delta must be 0.
    A panel in the flow fails here by exactly the pixels it took. The
    covering half wants the panel's horizontal span to overlap at least half
    the narrower of the two spans — half the editor's where the editor is
    smaller, half the panel's where a drawer anchored at the opposite edge
    spans less than half of a wide editor. A panel beside the editor, or
    meeting it by a single pixel, fails here.
    """
    if page.locator(panel_selector).count() == 0:
        pytest.fail(f"the panel selector matched nothing on {page.url}: {panel_selector}")
    if page.locator(editor_selector).count() == 0:
        pytest.fail(f"the editor selector matched nothing on {page.url}: {editor_selector}")
    panel = page.locator(panel_selector)
    editor = page.locator(editor_selector)
    # Closed first: hide, measure, restore, measure. The restore is the panel
    # the test goes on asserting about, so it happens before any failure.
    panel.evaluate("element => { element.style.display = 'none' }")
    closed = editor.bounding_box()
    panel.evaluate("element => { element.style.display = '' }")
    opened = editor.bounding_box()
    cover = panel.bounding_box()
    if closed is None or opened is None:
        pytest.fail(f"the editor is not visible on {page.url}: {editor_selector}")
    if cover is None:
        pytest.fail(f"the panel is not visible on {page.url}: {panel_selector}")
    delta = abs(opened["width"] - closed["width"])
    if delta != 0:
        pytest.fail(
            f"the panel squeezes the editor on {page.url}: width moves by "
            f"{delta}px ({closed['width']}px closed, {opened['width']}px open)"
        )
    overlap = min(cover["x"] + cover["width"], opened["x"] + opened["width"]) - max(
        cover["x"], opened["x"]
    )
    floor = min(cover["width"], opened["width"]) / 2
    vertical = (
        cover["y"] < opened["y"] + opened["height"] and opened["y"] < cover["y"] + cover["height"]
    )
    if overlap < floor or not vertical:
        pytest.fail(
            f"the panel does not lie onto the editor on {page.url}: overlaps "
            f"{overlap}px < {floor}px (panel at [{cover['x']}, {cover['width']}] "
            f"against editor at [{opened['x']}, {opened['width']}])"
        )
