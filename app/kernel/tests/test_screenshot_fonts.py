"""The capture's font rule, exercised without a browser.

``scripts.screenshots._assert_pinned_fonts`` evaluates the page; every
judgement it makes lives in ``scripts.screenshot_fonts`` so this module can
pin the first-family order, the visible/hidden rule and the command-glyph
refusal where no Playwright install is needed. The asset suite runs on a
checkout without the browser (#983), so the rule must travel with it.
"""

from __future__ import annotations

from scripts.screenshot_fonts import (
    COMMAND_GLYPH,
    PINNED_FAMILY,
    PINNED_WEIGHTS,
    MonoUse,
    first_family,
    validate_pinned_fonts,
)

LOADED: dict[int, bool] = dict.fromkeys(PINNED_WEIGHTS, True)
QUOTED = f'"{PINNED_FAMILY}", ui-monospace, SFMono-Regular, monospace'
BARE = f"{PINNED_FAMILY}, monospace"
SYSTEM_FIRST = f'ui-monospace, monospace, "{PINNED_FAMILY}"'


def test_a_frame_of_loaded_bundled_mono_passes() -> None:
    assert (
        validate_pinned_fonts(
            loaded=LOADED,
            mono_uses=[MonoUse(QUOTED, visible=True), MonoUse(BARE, visible=True)],
            body_text="Suchen K AI Assistant",
        )
        == []
    )


def test_a_missing_bundled_weight_fails_by_name() -> None:
    errors = validate_pinned_fonts(
        loaded={**LOADED, 500: False},
        mono_uses=[],
        body_text="",
    )
    assert errors == ["the bundled mono weights [500] did not load"]


def test_a_visible_system_first_mono_stack_fails() -> None:
    """Containing the bundled family is not enough; the first family paints."""
    errors = validate_pinned_fonts(
        loaded=LOADED,
        mono_uses=[MonoUse(SYSTEM_FIRST, visible=True)],
        body_text="",
    )
    assert len(errors) == 1
    assert SYSTEM_FIRST in errors[0]


def test_a_hidden_system_mono_stack_is_not_painted_and_does_not_fail() -> None:
    """display:none copy reaches no pixel, so it is not the capture's claim."""
    assert (
        validate_pinned_fonts(
            loaded=LOADED,
            mono_uses=[
                MonoUse(QUOTED, visible=True),
                MonoUse(SYSTEM_FIRST, visible=False),
            ],
            body_text="",
        )
        == []
    )


def test_the_same_stack_fails_only_once_however_many_elements_use_it() -> None:
    errors = validate_pinned_fonts(
        loaded=LOADED,
        mono_uses=[MonoUse(SYSTEM_FIRST, visible=True)] * 3,
        body_text="",
    )
    assert len(errors) == 1


def test_chromium_quoted_and_author_bare_families_are_the_same_face() -> None:
    assert first_family(QUOTED) == PINNED_FAMILY
    assert first_family(BARE) == PINNED_FAMILY
    assert first_family("'IBM Plex Mono', monospace") == PINNED_FAMILY
    assert first_family(SYSTEM_FIRST) != PINNED_FAMILY


def test_a_rendered_command_mark_fails() -> None:
    errors = validate_pinned_fonts(
        loaded=LOADED,
        mono_uses=[],
        body_text=f"Suchen {COMMAND_GLYPH}K",
    )
    assert errors == ["a rendered U+2318 command mark remains — it must be the SVG icon"]
