"""The screenshot capture's font contract, as pure validation.

The capture's determinism claim is narrower than "every glyph": the frames'
mono ink — keycaps, badges, code, dates and numeric metadata — must come from
the bundled IBM Plex Mono cuts, and the command mark must be the app's SVG
rather than U+2318 text. The UI sans and brand serif are bundled too, but the
guard does not name them: a missing serif or sans weight is a visual defect a
frame diff still catches, while a mono fallback was the environment-only
difference that opened no-op screenshot PRs.

``scripts.screenshots._assert_pinned_fonts`` evaluates the page and hands the
raw answers here, so the first-family order and the visible/hidden rule stay
testable without Playwright. FS-only tests import this module; it must never
import the capture stack.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

PINNED_FAMILY = "IBM Plex Mono"
"""The bundled face a rendered mono element must name first."""

PINNED_WEIGHTS = (400, 500, 600, 700)
"""The cuts the frames rely on; a missing one is a system fallback."""

COMMAND_GLYPH = "\u2318"
"""The command mark that must never reach the page as text."""

MONO_SCAN_JS = """async () => {
    const weights = [400, 500, 600, 700];
    await Promise.all(
        weights.map((weight) =>
            document.fonts.load(`${weight} 10px "IBM Plex Mono"`, "BESbswy"),
        ),
    );
    const loaded = Object.fromEntries(
        weights.map((weight) => [
            weight,
            document.fonts.check(`${weight} 10px "IBM Plex Mono"`, "BESbswy"),
        ]),
    );
    const monoUses = [];
    for (const element of document.querySelectorAll("body *")) {
        const family = getComputedStyle(element).fontFamily;
        if (!/mono/i.test(family)) continue;
        const style = getComputedStyle(element);
        const visible =
            typeof element.checkVisibility === "function"
                ? element.checkVisibility({
                      checkOpacity: true,
                      checkVisibilityCSS: true,
                      checkContentVisibility: true,
                  })
                : element.getClientRects().length > 0 &&
                  style.visibility !== "hidden" &&
                  Number(style.opacity) !== 0;
        monoUses.push({ family, visible });
    }
    return { loaded, monoUses, text: document.body.innerText };
}"""
"""The page evaluation the capture guard runs, as one expression.

``element.checkVisibility()`` without options answers "not ``display: none``"
in current Chromium: an element with ``visibility: hidden`` or ``opacity: 0``
still returns true and keeps client rects, and a system-mono stack there would
abort a capture that paints none of it. The explicit options make the scan's
meaning "paints pixels": the CSS visibility property, zero opacity and
``content-visibility: hidden`` all count as invisible. The fallback carries
the same meaning for a Chromium too old to support the options.

The expression lives here, not in the Playwright wrapper, so a real-browser
E2E can evaluate exactly what the capture evaluates.
"""


@dataclass(frozen=True, slots=True)
class MonoUse:
    """One element's computed font stack, and whether it is on screen."""

    family: str
    visible: bool


def first_family(stack: str) -> str:
    """The first family of a computed ``font-family`` stack, unquoted.

    Chromium serializes a family with spaces as ``"IBM Plex Mono"``; an
    author-written stack may carry the bare name or single quotes. All three
    name the same face, and only the first entry decides what paints.
    """
    first = stack.split(",", 1)[0].strip()
    if len(first) >= 2 and first[0] == first[-1] and first[0] in "\"'":
        first = first[1:-1]
    return first.strip()


def validate_pinned_fonts(
    *,
    loaded: Mapping[int, bool],
    mono_uses: Iterable[MonoUse],
    body_text: str,
) -> list[str]:
    """Every way a frame can bake in a machine-font glyph, as sentences.

    An empty list means the frame is capturable. Hidden elements are ignored:
    ``display: none`` copy (the phone-width chip, a closed menu) paints no
    pixels, and its family cannot reach the master. A visible element whose
    computed stack is mono must name the bundled face *first* — a stack that
    merely contains it behind a system family still paints the system face.
    """
    errors: list[str] = []

    missing = [weight for weight in PINNED_WEIGHTS if not loaded.get(weight)]
    if missing:
        errors.append(f"the bundled mono weights {missing} did not load")

    strays = sorted(
        {
            use.family
            for use in mono_uses
            if use.visible and first_family(use.family) != PINNED_FAMILY
        }
    )
    if strays:
        errors.append(f"a visible mono element falls back to a system face: {strays}")

    if COMMAND_GLYPH in body_text:
        errors.append("a rendered U+2318 command mark remains — it must be the SVG icon")

    return errors
