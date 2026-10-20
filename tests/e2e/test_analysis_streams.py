"""Analysis SSE specs — ANAL-005 coreference, ANAL-008 character voices,
and the CONS-001/ADR-044 consistency-stream content assertions the KB wave
deferred here.

Catalog (browser layer) for the validator-strict surfaces (E04:
coreference + character voices stream-die under TestModel; consistency
content is asserted deterministically), plus one REAL character-voice leg
whose deterministic PREFIX (the progress event) pins the N11 roster fix.

Run-affordance calibration (2026-10-19, live stack + panel sources):
- Panels auto-run on mount, and the ``?panel=`` URL-sync RESTORES (and
  auto-runs) the panel across ``reload_page`` (Task 8 fix round). Unlike
  ``test_analysis.py`` this module REUSES panel ids across legs (happy +
  error pairs share one id), so a restored panel would auto-run during
  ``prepare_ai_chapter`` — with the PREVIOUS leg's routes still
  registered. Every leg therefore closes the panel first
  (:func:`_close_analysis_panel`), keeping the auto-run inside the
  freshly-mocked open.
- The character-voice panel never renders the SSE progress string
  (``CharacterVoicePanel``'s loading state is static i18n text; the wire
  ``progress`` is stored display-only state no component mounts), so the
  REAL N11 pin rides the captured wire body (``expect_response``) instead
  of the DOM. The real router always terminates with ``[DONE]`` (in-band
  error events), so the captured body is complete.
- The consistency stage text renders only in the transient loading state
  — under the instant local-route mock the SSE events are processed in
  one React batch and the loading state never paints — so the ADR-044
  CONTENT pin asserts the captured wire's stage sequence (mirrors
  ``consistency_orchestrator.py``) plus the rendered result.

Runtime budget: ≤ 2.5 min (D-8). Markers: e2e.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import pytest

from tests.e2e.config import BASE_URL
from tests.e2e.foundation import NovelContext, make_authed_request
from tests.e2e.helpers import mock_llm
from tests.e2e.helpers.analysis_world import (
    N11_DIALOGUE_CHAPTER,
    open_analysis_panel,
)
from tests.e2e.helpers.editor_ai import prepare_ai_chapter
from tests.e2e.helpers.kb_world import seed_kb_entity
from tests.e2e.helpers.novel_factory import complete_wizard

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests as http_requests
    from playwright.sync_api import Page

_UI_WAIT_MS: int = 15_000

_URL_PANEL = re.compile(r"[?&]panel=([^&]+)")
"""The right panel active in the URL (``?panel=<id>``), or ``None``."""


def _close_analysis_panel(page: Page) -> None:
    """Close the open analysis panel (if any) before the next leg's reload.

    The ``?panel=`` URL-sync restores the panel after ``reload_page`` and
    the restored panel AUTO-RUNS on mount — with the previous leg's
    ``mock_llm`` routes still registered. This module's happy/error pairs
    share one panel id, so without this close the restored panel would
    answer its own assertions from the stale mock (or the real backend)
    during ``prepare_ai_chapter``, before this leg's mock is installed.
    """
    if _URL_PANEL.search(page.url) is None:
        return
    page.get_by_test_id("editor-right-panel").get_by_role(
        "button", name="Close", exact=True
    ).first.click()
    page.wait_for_url(lambda url: _URL_PANEL.search(str(url)) is None, timeout=_UI_WAIT_MS)


@pytest.fixture(scope="module")
def streams_novel(module_stable_user) -> NovelContext:
    novel = complete_wizard(module_stable_user.page, BASE_URL)
    return NovelContext(
        page=module_stable_user.page,
        novel_id=novel["novel_id"],
        email=module_stable_user.email,
        password=module_stable_user.password,
        access_token=module_stable_user.access_token,
    )


@pytest.fixture
def authed_request(
    api_request: Callable[..., http_requests.Response],
    streams_novel: NovelContext,
) -> Callable[..., http_requests.Response]:
    return make_authed_request(api_request, streams_novel)


@pytest.mark.e2e
class TestCoreference:
    def test_happy_path_renders_resolutions(self, streams_novel, authed_request) -> None:
        page = streams_novel.page
        _close_analysis_panel(page)
        prepare_ai_chapter(
            page,
            authed_request,
            streams_novel.novel_id,
            title="Coref Chapter",
            content=N11_DIALOGUE_CHAPTER,
        )
        mock_llm(page, "coreference_stream")
        open_analysis_panel(page, "coreference")

        page.get_by_text("92").first.wait_for(state="visible", timeout=20_000)
        assert page.get_by_text("Pronoun use is unambiguous").first.is_visible()

    def test_stream_error_renders_english_not_german(self, streams_novel, authed_request) -> None:
        """M05-class pin (fixed in Task 6): localized error copy."""
        page = streams_novel.page
        _close_analysis_panel(page)
        prepare_ai_chapter(
            page,
            authed_request,
            streams_novel.novel_id,
            title="Coref Error",
            content=N11_DIALOGUE_CHAPTER,
        )
        mock_llm(page, "coreference_stream", fixture="error")
        open_analysis_panel(page, "coreference")

        page.get_by_text("Connection lost. Check your internet connection.").first.wait_for(
            state="visible", timeout=20_000
        )
        assert page.get_by_text("Verbindung verloren").count() == 0


@pytest.mark.e2e
class TestCharacterVoices:
    def test_happy_path_renders_character_card(self, streams_novel, authed_request) -> None:
        page = streams_novel.page
        _close_analysis_panel(page)
        prepare_ai_chapter(
            page,
            authed_request,
            streams_novel.novel_id,
            title="Voices Chapter",
            content=N11_DIALOGUE_CHAPTER,
        )
        mock_llm(page, "character_voice_stream")
        open_analysis_panel(page, "character_voice")

        page.get_by_text(
            "Clipped countdown speech unlike the gatekeeper's formality."
        ).first.wait_for(state="visible", timeout=20_000)

    def test_real_stream_profiles_only_roster_characters(
        self, streams_novel, authed_request
    ) -> None:
        """N11 pin on the REAL stream: the deterministic prefix is honest.

        The progress event ("Profiling N character(s)") is emitted BEFORE
        any agent call, so this pin is immune to TestModel strictness
        (E04). The chapter's garbage attractors must NOT become profiles;
        the agent phase may legitimately die under TestModel afterwards —
        that tail is the documented E04 limitation, not a failure.

        The happy sibling's catalog mock is unrouted FIRST (routes survive
        reload_page on the shared module page — a leak would mock this
        REAL stream), and the pin rides the captured SSE body: the panel
        never renders the wire progress string (module docstring).
        """
        page = streams_novel.page
        # Unroute the happy sibling's catalog mock FIRST — routes survive
        # reload_page on the shared module page, and a surviving mock would
        # answer this REAL stream (the pin would ride the fixture, not the
        # real roster gate).
        page.unroute("**/api/v1/analysis/character-voice/*")
        _close_analysis_panel(page)
        seed_kb_entity(authed_request, streams_novel.novel_id, name="Elara")
        prepare_ai_chapter(
            page,
            authed_request,
            streams_novel.novel_id,
            title="N11 Chapter",
            content=N11_DIALOGUE_CHAPTER,
        )
        with page.expect_response(lambda r: "/api/v1/analysis/character-voice/" in r.url) as caught:
            open_analysis_panel(page, "character_voice")
        body = caught.value.text()

        # The roster gate held: exactly the seeded character is profiled —
        # the action-beat garbage attractors (Order / About / Ahead) are
        # demoted to speaker=None BEFORE this event is emitted, so a
        # broken gate would read "Profiling 4 character(s)" here.
        assert "Profiling 1 character" in body
        # No garbage profile cards — the roster gate held.
        for garbage in ("Order", "About", "Ahead"):
            assert page.get_by_text(re.compile(rf"^{garbage}$")).count() == 0


@pytest.mark.e2e
class TestConsistencyStream:
    def test_stage_sequence_and_result_content(self, streams_novel, authed_request) -> None:
        """CONS-001/ADR-044 content assertions (KB wave follow-through).

        Stage vocabulary mirrors consistency_orchestrator.py:
        extracting_facts → checking_consistency → result. The stage text
        renders only in the transient loading state (never painted under
        the instant local-route mock — module docstring), so the CONTENT
        pin rides the captured wire body; the result is additionally
        asserted in the rendered panel.
        """
        page = streams_novel.page
        _close_analysis_panel(page)
        prepare_ai_chapter(
            page,
            authed_request,
            streams_novel.novel_id,
            title="Consistency Chapter",
            content=N11_DIALOGUE_CHAPTER,
        )
        mock_llm(page, "consistency_stream")
        with page.expect_response(lambda r: "/api/v1/consistency/check/stream" in r.url) as caught:
            open_analysis_panel(page, "consistency")

        events = [
            json.loads(line.removeprefix("data: "))
            for line in caught.value.text().splitlines()
            if line.startswith("data: ") and line != "data: [DONE]"
        ]
        assert [e["stage"] for e in events if e.get("type") == "stage"] == [
            "extracting_facts",
            "checking_consistency",
        ]
        result = next(e for e in events if e.get("type") == "result")
        assert result["overall_assessment"] == "Consistent"
        assert result["total_issues"] == 0

        # Rendered result: the panel surfaces the assessment verbatim.
        page.get_by_text("Consistent").first.wait_for(state="visible", timeout=20_000)

    def test_stream_error_renders_english_not_german(self, streams_novel, authed_request) -> None:
        page = streams_novel.page
        _close_analysis_panel(page)
        prepare_ai_chapter(
            page,
            authed_request,
            streams_novel.novel_id,
            title="Consistency Error",
            content=N11_DIALOGUE_CHAPTER,
        )
        mock_llm(page, "consistency_stream", fixture="error")
        open_analysis_panel(page, "consistency")

        page.get_by_text("Connection lost. Check your internet connection.").first.wait_for(
            state="visible", timeout=20_000
        )
