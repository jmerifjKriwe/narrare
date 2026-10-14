"""AI-writing E2E specs — chapter generation (WRITE-002).

Drives the REAL generation panel against the real stack: the START POST and
accept/reject hit the real backend; the validator-strict generation STREAM
is deterministic via the browser-layer catalog (audit E04). Pins the three
fixed M06 behaviors (localized empty-input 422, stream-death error phase,
no empty-draft review) plus the happy accept/reject flows.

Runtime budget: ≤ 3 min (spec §7 — full suite ≤ 25 min). Markers: e2e.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.e2e.config import BASE_URL
from tests.e2e.foundation import NovelContext, make_authed_request
from tests.e2e.helpers import capture_network, mock_llm
from tests.e2e.helpers.editor_ai import (
    click_panel_generate,
    editor_text,
    open_generation_panel,
    prepare_ai_chapter,
)
from tests.e2e.helpers.novel_factory import complete_wizard

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests as http_requests


@pytest.fixture(scope="module")
def ai_novel(module_stable_user) -> NovelContext:
    """One wizard novel per module; tests create their own chapters."""
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
    ai_novel: NovelContext,
) -> Callable[..., http_requests.Response]:
    """``api_request`` carrying the module user's bearer token.

    Delegates to the foundation factory (extracted at the Task 9 third
    consumer; this module held the first copy).
    """
    return make_authed_request(api_request, ai_novel)


@pytest.mark.e2e
class TestGenerateFullDraft:
    def test_full_draft_happy_accept_inserts_into_editor(
        self, ai_novel: NovelContext, authed_request: Callable[..., http_requests.Response]
    ) -> None:
        page = ai_novel.page
        network = capture_network(page)
        mock_llm(page, "generation_stream")  # happy variant

        prepare_ai_chapter(page, authed_request, ai_novel.novel_id, title="Generate Happy")
        open_generation_panel(page)

        page.get_by_placeholder("What should the AI write about?").fill(
            "Elara waits at the sealed tide gate."
        )
        click_panel_generate(page)

        draft = page.locator(".ProseMirror, [contenteditable='true']").first
        page.get_by_text("harbour bell").first.wait_for(state="visible", timeout=30_000)
        page.get_by_role("button", name="Accept", exact=True).click()

        # The accepted draft lands in the editor (onDraftAccepted).
        page.wait_for_function(
            "() => document.querySelector('.ProseMirror')?.innerText.includes('harbour bell')",
            timeout=30_000,
        )
        assert "harbour bell" in editor_text(page)
        network.assert_no_provider_calls()
        assert draft.is_visible()

    def test_full_draft_reject_leaves_editor_unchanged(
        self, ai_novel: NovelContext, authed_request: Callable[..., http_requests.Response]
    ) -> None:
        page = ai_novel.page
        mock_llm(page, "generation_stream")

        chapter = prepare_ai_chapter(
            page,
            authed_request,
            ai_novel.novel_id,
            title="Generate Reject",
            content="Original opening line.",
        )
        open_generation_panel(page)

        page.get_by_placeholder("What should the AI write about?").fill("A rejected draft.")
        click_panel_generate(page)
        page.get_by_text("harbour bell").first.wait_for(state="visible", timeout=30_000)

        page.get_by_role("button", name="Reject", exact=True).click()
        # Reject shows the rating prompt; the editor keeps the original text.
        page.get_by_text("Rate this suggestion").first.wait_for(state="visible", timeout=15_000)
        assert editor_text(page).strip().startswith("Original opening line.")
        assert "harbour bell" not in editor_text(page)
        assert chapter["title"]


@pytest.mark.e2e
class TestGenerateErrorPaths:
    def test_empty_form_shows_localized_validation_not_connection_lost(
        self, ai_novel: NovelContext, authed_request: Callable[..., http_requests.Response]
    ) -> None:
        """M06 pin: empty-form 422 MISSING_INPUT renders the honest localized
        message (was: hardcoded German 'connection lost')."""
        page = ai_novel.page
        network = capture_network(page)

        prepare_ai_chapter(page, authed_request, ai_novel.novel_id, title="Generate Empty 422")
        open_generation_panel(page)

        click_panel_generate(page)  # empty form

        # Scoped to the panel: unrelated empty [role=alert] live regions exist
        # elsewhere on the page (toaster), and only the panel's error phase
        # renders the M06 localized validation message.
        alert = page.get_by_test_id("editor-right-panel").get_by_role("alert")
        alert.wait_for(state="visible", timeout=15_000)
        assert (
            "At least one of outline, prompt, or auto-continue must be provided."
            in alert.inner_text()
        ), "M06: the empty-form 422 must map to generationPanel.validationMissingInput"
        assert "Verbindung" not in alert.inner_text(), (
            "M06: German connection-lost fallback must be gone"
        )
        network.assert_no_api_failures(allow_statuses=(422,))  # the real backend 422 is expected

    def test_stream_http_error_shows_error_phase_without_accept(
        self, ai_novel: NovelContext, authed_request: Callable[..., http_requests.Response]
    ) -> None:
        """M06 pin: an HTTP-500 generation stream lands in the error phase
        with Retry — never a review phase with Accept."""
        page = ai_novel.page
        mock_llm(page, "generation_stream", fixture="error")

        prepare_ai_chapter(page, authed_request, ai_novel.novel_id, title="Generate Stream 500")
        open_generation_panel(page)

        page.get_by_placeholder("What should the AI write about?").fill("A doomed generation.")
        click_panel_generate(page)

        page.get_by_role("button", name="Retry", exact=True).wait_for(
            state="visible", timeout=30_000
        )
        assert page.get_by_role("button", name="Accept", exact=True).count() == 0, (
            "M06: the error phase must not offer Accept"
        )

    def test_truncated_stream_never_reaches_review_with_empty_draft(
        self, ai_novel: NovelContext, authed_request: Callable[..., http_requests.Response]
    ) -> None:
        """M06 pin (the audit repro): a stream that ends silently — no text,
        no is_final — must produce the error phase, not 'Waiting for AI
        response…' with an enabled Accept."""
        page = ai_novel.page
        mock_llm(page, "generation_stream", fixture="truncated")

        prepare_ai_chapter(page, authed_request, ai_novel.novel_id, title="Generate Truncated")
        open_generation_panel(page)

        page.get_by_placeholder("What should the AI write about?").fill("A silent death.")
        click_panel_generate(page)

        page.get_by_role("button", name="Retry", exact=True).wait_for(
            state="visible", timeout=30_000
        )
        assert page.get_by_role("button", name="Accept", exact=True).count() == 0
