"""Analysis-surface prep for the analysis E2E specs (spec §4 helpers).

Owns the recurring analysis concerns so the three spec files assert
instead of navigating: toolbar panel entry, N11 repro prose, sentiment
model-presence guard (spec §10 skipif), and voice-profile seeding via
the KB PATCH API (character-voice cannot seed profiles under TestModel —
E04 stream death precedes persistence — so drift/check specs seed the
``speech.voice_analysis`` block directly, the KB wave's D-8 discipline).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests
    from playwright.sync_api import Page

_UI_WAIT_MS: int = 15_000

# Toolbar trigger accessible names — packages/i18n/messages/en/analysis.json
# (verified 2026-10-18 live: every *Trigger.tsx sets
# ``aria-label={t("<panel>.triggerTooltip")}``, and an aria-label OVERRIDES
# the visible <span>{trigger}</span> as the button's accessible name — so
# ``get_by_role("button", name=…)`` must match the TOOLTIP string, not the
# short visible label. Re-calibrate if the tooltips drift.)
ANALYSIS_TRIGGERS: dict[str, str] = {
    "beta_reader": "Get AI-powered feedback as if from a beta reader",
    "sentiment": "Analyze emotional tone and sentiment of your text",
    "consistency": "Check your text for character, timeline, world, and plot inconsistencies",
    "readability": "Analyze text complexity and get readability scores",
    "pov": "Detect POV character, head-hopping, and knowledge leakage",
    "coreference": "Analyze pronoun clarity and resolve character references",
    "character_voice": "Analyze character dialogue to create voice profiles for consistency",
    "voice_check": "Check if dialogue matches each character's established voice profile",
    "voice_drift": "Track how each character's voice drifts across chapters",
    "author_voice": (
        "Analyze your narrative voice and create an author-voice profile for AI generation"
    ),
    "author_voice_drift": "Track how your narrative voice drifts across chapters",
}


def open_analysis_panel(page: Page, panel: str) -> None:
    """Open an analysis right-panel from its toolbar trigger button.

    Clicks by the button's accessible name (the aria-label tooltip —
    see ``ANALYSIS_TRIGGERS``).
    """
    page.get_by_role("button", name=ANALYSIS_TRIGGERS[panel], exact=True).click()
    page.get_by_test_id("editor-right-panel").wait_for(state="visible", timeout=_UI_WAIT_MS)


def sentiment_models_available() -> bool:
    """True when the spaCy EN model the provider maps to is installed.

    CI's test-e2e installs the models (W3-2 cache); a bare local venv does
    not — the guard keeps the deterministic happy-path specs honest in
    both (spec §10; E03 degradation is integration-pinned in Task 3).
    """
    try:
        import spacy

        return bool(spacy.util.is_package("en_core_web_md"))
    except Exception:
        # Bare absence IS the signal — any import/lookup failure means
        # "models not available" and the spec leg skips (E03 stance, D-3).
        return False


# N11 repro: sentence-initial capitalized words directly before quotes —
# the action-beat heuristic's garbage attractors. "Elara" is the only
# roster character in every spec that seeds a KB entry by that name.
N11_DIALOGUE_CHAPTER = (
    'Elara pressed her palm against the gate. "Open it," she said.\n\n'
    'In order to be ready, she counted the bells. "Two strikes. The gate, then."\n\n'
    'About an hour later, the guard sighed. "Nobody crosses after dark."\n\n'
    'Ahead of her, torchlight guttered. Elara said, "Then I make an exception."'
)

# ~60 words: below the beta-reader 1000-word minimum (N13 boundary).
SHORT_CHAPTER = (
    "Elara waited by the gate. The bells rang twice, and she counted "
    "them the way her mother had taught her, waiting for the third "
    "before she stepped into the dark."
)

# Multi-sentence emotional prose for the deterministic sentiment run.
RICH_CHAPTER = (
    "Elara was furious when the gate stayed shut. She screamed at the "
    "guard, joyful for a moment when the lock clicked, then terrified "
    'of the dark road beyond. "Open it," she said, calm again. The '
    "guard laughed. She wept, quietly, and waited for the third bell."
)


def seed_voice_profile(
    authed_request: Callable[..., requests.Response],
    novel_id: str,
    entry_id: str,
    voice_analysis: dict,
) -> dict:
    """Write ``speech.voice_analysis`` onto a KB character via PATCH.

    The drift/check pipelines read stored profiles through the ADR-050
    consumer; this seeds one deterministically (the shape mirrors the
    catalog's validated ``voice_analysis`` block).
    """
    resp = authed_request(
        "PATCH",
        f"/api/v1/novels/{novel_id}/kb/entries/{entry_id}",
        json={"metadata": {"speech": {"voice_analysis": voice_analysis}}},
    )
    assert resp.status_code == 200, f"{resp.status_code} {resp.text[:300]}"
    return resp.json()


__all__ = [
    "ANALYSIS_TRIGGERS",
    "N11_DIALOGUE_CHAPTER",
    "RICH_CHAPTER",
    "SHORT_CHAPTER",
    "open_analysis_panel",
    "seed_voice_profile",
    "sentiment_models_available",
]
