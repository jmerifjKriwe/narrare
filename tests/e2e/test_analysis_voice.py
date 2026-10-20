"""Voice-family specs — ANAL-007 author voice, ANAL-009 author voice drift,
ANAL-009 character voice drift, and the voice check (WRITE-010 surface).

All four run the REAL backend under TestModel (D-7; audit "Verified WORKING":
author voice, author drift, check voice; voice drift rides its deterministic
progress prefix plus the service-assembled ``character_result`` — the
agent-authored classification fields are asserted structurally only, never
by content). Stored character profiles are seeded via the KB PATCH API
(character-voice cannot seed them under TestModel — E04; D-7 discipline).
The stored AUTHOR-voice profile the drift leg needs has no REST write path
(the AuthorVoicePanel docstring records the missing routes), so that leg
seeds it by a REAL author-voice stream POST — persistence (ADR-074) happens
before the stream's ``result`` event, so the probe body proves the seed.

Run-affordance calibration (2026-10-20, live stack + panel sources + wire):
- Unlike the beta-reader family (auto-run on mount), all four voice panels
  are ON-DEMAND: they mount into an idle state and wait for an in-panel run
  button. The run click is scoped to ``editor-right-panel`` because toolbar
  aria-labels contain "Analyze" (sentiment / readability / coreference /
  character-voice / author-voice tooltips) and the voice-check toolbar toggle
  shares the in-panel run button's exact accessible name ("Check character
  voices") — an unscoped ``.first`` click would hit a toolbar trigger and
  toggle the panel closed (``?panel=`` toggle trap, Task 8).
- SSE streams answer 200 even when the analysis dies in-band ("… analysis
  failed." event before ``[DONE]``), so status alone would lie: three legs
  assert the router's error string is ABSENT (liveness), while the check leg
  asserts it PRESENT — that stream's agent phase is the documented E04 tail
  (see :class:`TestVoiceCheck`). The real routers always terminate with
  ``[DONE]``, so the captured body is complete (Task 9 verified pattern).
- "Elara" DOM probes are scoped to ``editor-right-panel``: the chapter prose
  (N11_DIALOGUE_CHAPTER) contains "Elara" in the editor, and an unscoped
  ``get_by_text`` matches that first (Task 8 fix-round finding).
- Wire calibration: drift progress reads "Analysing voice drift for
  1 character(s)" (roster-gated), check progress reads "… for 1 speaking
  character(s) (1 with stored profiles)." — the N11 counts are pre-agent
  and therefore TestModel-immune (inverted RED probes confirmed both).
- KB seeding is idempotent per module novel (a second "Elara" POST 409s on
  the slug conflict — live-verified), so drift and check share one
  module-scoped seed instead of seeding per test under pytest-randomly.

Runtime budget: ≤ 2 min (D-8). Markers: e2e.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from tests.e2e.config import BASE_URL
from tests.e2e.foundation import NovelContext, make_authed_request
from tests.e2e.helpers.analysis_world import (
    N11_DIALOGUE_CHAPTER,
    open_analysis_panel,
    seed_voice_profile,
)
from tests.e2e.helpers.editor_ai import prepare_ai_chapter
from tests.e2e.helpers.kb_world import seed_kb_entity
from tests.e2e.helpers.novel_factory import complete_wizard

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests as http_requests
    from playwright.sync_api import Page

# Validated voice_analysis block (mirrors the catalog fixture, which the
# §10 ratchet validates against the real VoiceAnalysis model).
_VOICE_ANALYSIS = {
    "formality": 0.3,
    "vocabulary_level": "moderate",
    "sentence_profile": "varied",
    "emotional_range": "expressive",
    "cultural_regional_markers": "harbour-town idioms",
    "voice_examples": ["Two strikes. The gate, then."],
    "voice_metrics": {
        "avg_sentence_length": 11.2,
        "sentence_length_std": 4.1,
        "type_token_ratio": 0.62,
        "avg_syllables_per_word": 1.4,
        "contraction_rate": 0.21,
        "verbal_tic_frequency": {"Two strikes": 0.08},
        "punctuation_profile": {"ellipsis": 0.02},
    },
}

# In-band SSE failure strings (router_author_voice.py:97, router_author_voice_
# drift.py:109, router_voice_drift.py:100, router_voice_check.py:69). A dead
# stream still answers 200 — the absence of these is the honest liveness pin.
_ERROR_STRINGS = {
    "author_voice": "Author-voice analysis failed.",
    "author_voice_drift": "Author-voice-drift analysis failed.",
    "voice_drift": "Voice-drift analysis failed.",
    "voice_check": "Voice-check analysis failed.",
}


def _run_in_panel(page: Page, name: str) -> None:
    """Click an in-panel run button by exact accessible name.

    Panel-scoped on purpose: the toolbar triggers' aria-labels contain
    "Analyze"/"Check" and would win an unscoped ``.first`` query — clicking
    one toggles the panel instead of running the analysis (module docstring).
    """
    page.get_by_test_id("editor-right-panel").get_by_role("button", name=name, exact=True).click()


@pytest.fixture(scope="module")
def voice_novel(module_stable_user) -> NovelContext:
    novel = complete_wizard(module_stable_user.page, BASE_URL)
    return NovelContext(
        page=module_stable_user.page,
        novel_id=novel["novel_id"],
        email=module_stable_user.email,
        password=module_stable_user.password,
        access_token=module_stable_user.access_token,
    )


@pytest.fixture(scope="module")
def seeded_elara(
    api_session: http_requests.Session,
    api_url: str,
    voice_novel: NovelContext,
) -> str:
    """Seed the Elara roster entry + stored voice profile once per module.

    Drift and check both need the SAME named character (the roster gate and
    the profile lookup match on the dialogue's speaker name), and a second
    "Elara" POST answers 409 CONFLICT on the slug — so under pytest-randomly
    the seed must happen exactly once. Built on the session-scoped
    ``api_session``/``api_url`` pair (what ``api_request`` closes over)
    because a module-scoped fixture cannot request the function-scoped
    ``api_request``; the bearer token scopes every call to THIS novel's
    owner, same contract as :func:`make_authed_request`.
    """

    def _module_request(method: str, path: str, **kwargs: object) -> http_requests.Response:
        session_request: Callable[..., http_requests.Response] = api_session.request
        return session_request(
            method,
            f"{api_url}{path}",
            headers={"Authorization": f"Bearer {voice_novel.access_token}"},
            **kwargs,
        )

    entry = seed_kb_entity(_module_request, voice_novel.novel_id, name="Elara")
    seed_voice_profile(_module_request, voice_novel.novel_id, entry["id"], _VOICE_ANALYSIS)
    return entry["id"]


@pytest.fixture
def authed_request(
    api_request: Callable[..., http_requests.Response],
    voice_novel: NovelContext,
) -> Callable[..., http_requests.Response]:
    return make_authed_request(api_request, voice_novel)


@pytest.mark.e2e
class TestAuthorVoice:
    def test_profile_generates_and_renders(self, voice_novel, authed_request) -> None:
        page = voice_novel.page
        prepare_ai_chapter(
            page,
            authed_request,
            voice_novel.novel_id,
            title="Author Voice Chapter",
            content=N11_DIALOGUE_CHAPTER,
        )
        open_analysis_panel(page, "author_voice")

        with page.expect_response(
            lambda r: "/analysis/author-voice" in r.url, timeout=60_000
        ) as caught:
            _run_in_panel(page, "Analyze Voice")
        assert caught.value.status == 200
        body = caught.value.text()
        assert _ERROR_STRINGS["author_voice"] not in body
        # The result event carries the assembled profile; persistence (ADR-074)
        # precedes the yield, so this doubles as the profile-stored pin.
        assert '"result"' in body
        page.get_by_test_id("editor-right-panel").get_by_text("Voice Profile").first.wait_for(
            state="visible", timeout=30_000
        )


@pytest.mark.e2e
class TestAuthorVoiceDrift:
    def test_narrator_trend_renders(self, voice_novel, authed_request) -> None:
        page = voice_novel.page
        prepare_ai_chapter(
            page,
            authed_request,
            voice_novel.novel_id,
            title="Drift Chapter",
            content=N11_DIALOGUE_CHAPTER,
        )
        # Seed the stored author-voice profile through its ONLY write path —
        # a REAL author-voice stream run. There is no REST seed route, and
        # pytest-randomly forbids relying on TestAuthorVoice having run first
        # (live-verified: drift without a stored profile answers a graceful
        # no_profile, which renders "No author-voice profile", not a trend).
        probe = authed_request(
            "POST",
            f"/api/v1/analysis/author-voice/{voice_novel.novel_id}",
            json={"chapter_ids": None},
        )
        assert probe.status_code == 200
        probe_body = probe.text
        assert _ERROR_STRINGS["author_voice"] not in probe_body
        assert '"result"' in probe_body

        open_analysis_panel(page, "author_voice_drift")
        with page.expect_response(
            lambda r: "/analysis/author-voice-drift" in r.url, timeout=60_000
        ) as caught:
            _run_in_panel(page, "Analyze")
        assert caught.value.status == 200
        body = caught.value.text()
        assert _ERROR_STRINGS["author_voice_drift"] not in body
        # The trend branch, not the graceful no-profile skip — pin the EVENT
        # name, not the bare string: the SSE envelope serializes
        # "no_profile": null on every event of every stream (live-verified).
        assert '"event": "no_profile"' not in body
        assert '"result"' in body
        panel = page.get_by_test_id("editor-right-panel")
        panel.get_by_text(re.compile("chapters analyzed")).first.wait_for(
            state="visible", timeout=30_000
        )
        assert panel.get_by_text("Drift trend").first.is_visible()


@pytest.mark.e2e
class TestVoiceDrift:
    def test_roster_only_characters_in_events(
        self, voice_novel, authed_request, seeded_elara
    ) -> None:
        """N11 panel pin: KB character + stored profile → drift result;
        garbage speakers never enter the character set (fixed in-wave)."""
        page = voice_novel.page
        prepare_ai_chapter(
            page,
            authed_request,
            voice_novel.novel_id,
            title="Voice Drift Chapter",
            content=N11_DIALOGUE_CHAPTER,
        )
        open_analysis_panel(page, "voice_drift")

        # API probe (deterministic prefix): progress names exactly the roster
        # character — emitted BEFORE any agent call, so TestModel-immune.
        with page.expect_response(
            lambda r: "/analysis/voice-drift" in r.url, timeout=60_000
        ) as caught:
            _run_in_panel(page, "Analyze")
        assert caught.value.status == 200
        body = caught.value.text()
        assert _ERROR_STRINGS["voice_drift"] not in body
        assert "Analysing voice drift for 1 character" in body
        assert "Elara" in body
        for garbage in ("Order", "About", "Ahead"):
            assert garbage not in body, f"N11 regression: {garbage} leaked into the stream"

        # Panel leg: the overview row for Elara renders (heatmaps exist
        # only for profiled characters — the audit's list-fallback note).
        page.get_by_test_id("editor-right-panel").get_by_text("Elara").first.wait_for(
            state="visible", timeout=30_000
        )


@pytest.mark.e2e
class TestVoiceCheck:
    def test_check_matches_seeded_profile(self, voice_novel, authed_request, seeded_elara) -> None:
        """REAL check stream with a KB-PATCH-seeded profile (N11 pt2 surface).

        The stream's deterministic prefix is the pin: the progress count
        "1 speaking character(s) (1 with stored profiles)" is emitted AFTER
        the roster gate (garbage attractors demoted — pre-fix it read
        "4 speaking") and after the ADR-050 consumer read the PATCHed
        profile — both pre-agent, therefore TestModel-immune (inverted RED
        probe confirmed the discriminator).

        E04 tail (documented, same stance as Task 9's real character-voice
        leg): the checker agent is validator-strict — its output validator
        raises ModelRetry when no entry carries a non-empty character_name,
        the one invariant TestModel's synthesized output cannot satisfy — so
        the agent phase ALWAYS dies in-band ("Voice-check analysis failed.",
        ModelRetryExhaustedError — live-verified twice) BEFORE the result
        events. The leg therefore pins the panel's honest degradation
        instead of a result card — which also live-pins this panel's M05 EN
        error copy.
        """
        page = voice_novel.page
        prepare_ai_chapter(
            page,
            authed_request,
            voice_novel.novel_id,
            title="Check Chapter",
            content=N11_DIALOGUE_CHAPTER,
        )
        open_analysis_panel(page, "voice_check")

        with page.expect_response(
            lambda r: "/analysis/voice-check" in r.url, timeout=60_000
        ) as caught:
            _run_in_panel(page, "Check character voices")
        assert caught.value.status == 200
        body = caught.value.text()
        assert "for 1 speaking character(s) (1 with stored profiles)" in body
        # The in-band death is the DOCUMENTED E04 tail — asserted present so
        # a future regression to a hanging/empty stream fails loudly too.
        assert _ERROR_STRINGS["voice_check"] in body
        page.get_by_test_id("editor-right-panel").get_by_text(
            "Failed to check character voices"
        ).first.wait_for(state="visible", timeout=30_000)
