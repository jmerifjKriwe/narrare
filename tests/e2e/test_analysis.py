"""Analysis E2E specs — ANAL-001 beta reader, ANAL-002 sentiment,
ANAL-003 readability, ANAL-004 POV (spec §5 row ``test_analysis.py``).

Real backend under TestModel for readability/POV/sentiment (ADR-021
deterministic or tolerance-loose); the browser-layer catalog for the
validator-strict beta reader (E04). Pins: B07 (POV kb-supply — FIXED in
the blocker wave; pinned green), E03 (sentiment model-presence stance,
D-3), N12 (readability composes the full response model — fixed in-wave),
N13 (min-words
422 machine-readable — fixed in-wave).

Run-affordance calibration (2026-10-18, live panel components): ALL FOUR
panels auto-run on mount — ``BetaReaderPanel``/``SentimentPanel``/
``ReadabilityPanel``/``POVPanel`` each call ``runAnalysis(false)`` from a
mount-only ``useEffect`` when idle, and expose NO "Analyze"/"Run" button
(only the header "Refresh Analysis" in the results state and a "Try
Again" in the error state). The brief's anticipated run-button clicks are
therefore replaced: ``expect_response`` wraps ``open_analysis_panel`` —
the toolbar-trigger click is what mounts the panel and fires the POST.

Runtime budget: ≤ 2.5 min (spec §7 / D-8). Markers: e2e.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from tests.e2e.config import BASE_URL
from tests.e2e.foundation import NovelContext, make_authed_request
from tests.e2e.helpers import mock_llm
from tests.e2e.helpers.analysis_world import (
    N11_DIALOGUE_CHAPTER,
    RICH_CHAPTER,
    SHORT_CHAPTER,
    open_analysis_panel,
    sentiment_models_available,
)
from tests.e2e.helpers.editor_ai import prepare_ai_chapter
from tests.e2e.helpers.novel_factory import complete_wizard

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests as http_requests


@pytest.fixture(scope="module")
def analysis_novel(module_stable_user) -> NovelContext:
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
    analysis_novel: NovelContext,
) -> Callable[..., http_requests.Response]:
    return make_authed_request(api_request, analysis_novel)


@pytest.mark.e2e
class TestBetaReader:
    def test_happy_path_renders_mocked_feedback(self, analysis_novel, authed_request) -> None:
        page = analysis_novel.page
        prepare_ai_chapter(
            page,
            authed_request,
            analysis_novel.novel_id,
            title="Beta Chapter",
            content=N11_DIALOGUE_CHAPTER,
        )
        mock_llm(page, "beta_reader")
        open_analysis_panel(page, "beta_reader")

        # The panel auto-runs on the active chapter (catalog-mocked).
        page.get_by_text("Elara's motivation is concrete").first.wait_for(
            state="visible", timeout=20_000
        )
        # The overall summary renders ONLY on the "Overall" tab — the
        # panel's default tab is "strengths" (BetaReaderPanel.tsx
        # ``useState<BetaTab>("strengths")``; calibration 2026-10-18).
        page.get_by_role("button", name="Overall", exact=True).click()
        page.get_by_text("A focused opening scene with one clear objective.").first.wait_for(
            state="visible", timeout=10_000
        )
        assert page.get_by_text(
            "A focused opening scene with one clear objective."
        ).first.is_visible()

    def test_below_minimum_words_answers_422_machine_readable(
        self, analysis_novel, authed_request
    ) -> None:
        """N13 pin (fixed in-wave): the business rule is honest on the wire.

        NO catalog mock installed — the REAL backend must validate. The
        panel auto-runs on mount, so the POST (and its 422) fire while the
        panel opens (see module docstring calibration).
        """
        page = analysis_novel.page
        # Deterministic real-backend pin: pytest-randomly may run the
        # happy-path sibling FIRST, and its ``mock_llm`` routes survive
        # navigation on this shared module page — a leaking beta-reader
        # mock would fulfill THIS request with a mocked 200 before the
        # real backend's 422 ever happens (same leak class as the
        # unroute comment in test_auth_flow.py). Strip the pattern first.
        page.unroute("**/api/v1/analysis/beta-reader*")
        prepare_ai_chapter(
            page,
            authed_request,
            analysis_novel.novel_id,
            title="Too Short",
            content=SHORT_CHAPTER,
        )
        with page.expect_response(lambda r: "/api/v1/analysis/beta-reader" in r.url) as caught:
            open_analysis_panel(page, "beta_reader")
        resp = caught.value
        assert resp.status == 422
        body = resp.json()
        assert body["code"] == "WORD_COUNT_BELOW_MINIMUM"


@pytest.mark.e2e
class TestSentiment:
    @pytest.mark.skipif(
        not sentiment_models_available(),
        reason="spaCy en_core_web_md not installed — run `just install-nlp-models`; "
        "CI test-e2e installs the models (E03 stance, D-3; degradation is "
        "integration-pinned in the fix task)",
    )
    def test_deterministic_scores_render(self, analysis_novel, authed_request) -> None:
        page = analysis_novel.page
        prepare_ai_chapter(
            page,
            authed_request,
            analysis_novel.novel_id,
            title="Mood Chapter",
            content=RICH_CHAPTER,
        )

        with page.expect_response(lambda r: "/api/v1/analysis/sentiment" in r.url) as caught:
            open_analysis_panel(page, "sentiment")
        resp = caught.value
        assert resp.status == 200
        overview = resp.json()[0]
        assert overview["sentence_count"] >= 1
        assert "average_vad" in overview
        # Data-quality warning is part of the deterministic contract
        # (< 500 words → warning; ADR-021).
        assert any("500" in w for w in overview.get("warnings", []))
        # UI label calibration: sentiment.sentences renders as
        # "Sentence Breakdown ({count})" — the brief's "Sentences|sentences"
        # regex matches no rendered EN string.
        page.get_by_text(re.compile("Sentence Breakdown")).first.wait_for(
            state="visible", timeout=15_000
        )


@pytest.mark.e2e
class TestReadability:
    def test_metrics_and_ai_phase_on_the_real_path(self, analysis_novel, authed_request) -> None:
        """N12 pin (fixed in-wave): 200 + metrics + full response model composed.

        This layer pins the composed response model (metrics + the
        ``sentence_analyses`` field); discriminating AI-phase-ran vs
        honest-skip is the unit level's job.
        """
        page = analysis_novel.page
        prepare_ai_chapter(
            page,
            authed_request,
            analysis_novel.novel_id,
            title="Readability Chapter",
            content=RICH_CHAPTER,
        )

        with page.expect_response(lambda r: "/api/v1/analysis/readability" in r.url) as caught:
            open_analysis_panel(page, "readability")
        resp = caught.value
        assert resp.status == 200
        result = resp.json()[0]
        assert isinstance(result["metrics"]["flesch_reading_ease"], (int, float))
        # The AI phase now composes (Task 1). Under TestModel the agent
        # output is schema-generated: assert the KEY is present; the
        # count may be 0 only if TestModel synthesizes an empty list —
        # record the observed value in the report and, if 0, keep the
        # key-presence assertion + note (honest pin, no hard-fail on a
        # TestModel artifact).
        assert "sentence_analyses" in result
        page.get_by_text(re.compile("Flesch|Reading Ease")).first.wait_for(
            state="visible", timeout=15_000
        )


@pytest.mark.e2e
class TestPOV:
    def test_real_path_answers_200_b07_fixed(self, analysis_novel, authed_request) -> None:
        """B07 pin: the kb-supply fix holds — 200 POVResult, no 500."""
        page = analysis_novel.page
        # Deterministic real-backend pin: strip any catalog pov mock a
        # randomly-ordered sibling (test_panel_renders_deterministic_
        # content) left on this shared page — handlers survive navigation
        # and would fulfill this request with the mocked body (same leak
        # class as test_auth_flow.py's unroute).
        page.unroute("**/api/v1/analysis/pov*")
        prepare_ai_chapter(
            page,
            authed_request,
            analysis_novel.novel_id,
            title="POV Chapter",
            content=N11_DIALOGUE_CHAPTER,
        )

        with page.expect_response(lambda r: "/api/v1/analysis/pov" in r.url) as caught:
            open_analysis_panel(page, "pov")
        resp = caught.value
        assert resp.status == 200, f"B07 regression: {resp.status} {resp.text[:200]}"
        result = resp.json()
        assert "pov_distribution" in result and "scenes" in result

    def test_panel_renders_deterministic_content(self, analysis_novel, authed_request) -> None:
        """Panel-content leg via the catalog (independent of TestModel)."""
        page = analysis_novel.page
        prepare_ai_chapter(
            page,
            authed_request,
            analysis_novel.novel_id,
            title="POV Content",
            content=N11_DIALOGUE_CHAPTER,
        )
        mock_llm(page, "pov")
        open_analysis_panel(page, "pov")

        # Catalog-UNIQUE string, scoped to the right panel. The seeded
        # chapter prose itself contains "Elara", so a bare get_by_text
        # matched the EDITOR and proved nothing about the panel. The
        # issue excerpt exists only in the pov catalog fixture (rendered
        # via pov.quotedExcerpt in POVIssueRow).
        page.get_by_test_id("editor-right-panel").get_by_text(
            "The gatekeeper doubted her story."
        ).first.wait_for(state="visible", timeout=20_000)
