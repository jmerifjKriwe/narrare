"""The capture guard's painted-state rule, in a real browser.

The pure rule trusts the ``visible`` flag it is handed; only the browser can
answer which elements paint. ``page.evaluate`` here runs the exact expression
``scripts.screenshots._assert_pinned_fonts`` runs. ``checkVisibility()`` with
no options would call all four probes below visible — that is the regression
this leg exists for. A hidden element paints no pixel, so a system-mono stack
there must not abort a capture.

No stack is started: the expression needs a document and fonts, nothing else.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from scripts.screenshot_fonts import MONO_SCAN_JS

if TYPE_CHECKING:
    from playwright.sync_api import Page

pytestmark = pytest.mark.e2e

PROBES = """
<div style="font-family: monospace">painted</div>
<div style="font-family: ui-monospace; display: none">display none</div>
<div style="font-family: monospace, serif; visibility: hidden">visibility hidden</div>
<div style="font-family: ui-monospace, monospace; opacity: 0">opacity zero</div>
"""

PAINTED = "monospace"
UNPAINTED = {"ui-monospace", "monospace, serif", "ui-monospace, monospace"}


def test_the_scan_counts_only_painted_mono_elements(page: Page) -> None:
    page.set_content(PROBES)
    result = page.evaluate(MONO_SCAN_JS)

    painted = {use["family"] for use in result["monoUses"] if use["visible"]}
    unpainted = {use["family"] for use in result["monoUses"] if not use["visible"]}

    assert painted == {PAINTED}, "a visible probe was dropped or a hidden one counted"
    assert unpainted == UNPAINTED, "display:none, visibility:hidden and opacity:0 must stay hidden"
