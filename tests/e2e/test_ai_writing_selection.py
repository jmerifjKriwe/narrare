"""AI-writing E2E specs — selection tools: extend, rewrite, co-author, unblock.

WRITE-003 extend (B08 pin: toolbar wiring), WRITE-004 rewrite (B01 pin:
500-char context compliance, modal/preview reachable, Replace applies).
Extend runs on the TestModel factory layer (tolerance-loose, spec §3);
rewrite is deterministic via the browser-layer catalog (FE parses
``<alternative>`` tags — TestModel output would be junk for Apply paths).

Entry-point note (Task 4 carry-over): the rewrite flow drives the REAL
bubble menu (the "AI rewrite" button lives in TipTapBubbleMenu, shown on
a live selection); the bubble-menu CO-AUTHOR entry branch (``onCoAuthor``)
is not touched by this module and stays owed to the co-author/unblock spec.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.e2e.config import BASE_URL
from tests.e2e.foundation import NovelContext
from tests.e2e.helpers import capture_network, mock_llm
from tests.e2e.helpers.editor_ai import editor_text, focus_editor_end, prepare_ai_chapter
from tests.e2e.helpers.novel_factory import complete_wizard

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests as http_requests

_EXTEND_SEED = (
    "The harbour bell rang twice before dawn, and Elara counted the strikes "
    "the way her mother had taught her. Two strikes meant the tide gate would "
    "seal within the hour."
)


@pytest.fixture(scope="module")
def sel_novel(module_stable_user) -> NovelContext:
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
    sel_novel: NovelContext,
) -> Callable[..., http_requests.Response]:
    """``api_request`` carrying the module user's bearer token.

    The conftest ``api_request`` is deliberately unauthenticated (shared
    session); chapter seeding must land on THIS user's novel — the same
    suite convention test_ai_writing.py uses (http_session.py pattern).
    """

    def _request(method: str, path: str, **kwargs: object) -> http_requests.Response:
        return api_request(
            method,
            path,
            headers={"Authorization": f"Bearer {sel_novel.access_token}"},
            **kwargs,
        )

    return _request


@pytest.mark.e2e
class TestExtend:
    def test_continue_writing_appends_text_at_caret(
        self, sel_novel: NovelContext, authed_request: Callable[..., http_requests.Response]
    ) -> None:
        """B08 pin: the toolbar Continue button is wired and streams into the
        editor (pre-fix: never rendered / stub no-op)."""
        page = sel_novel.page
        network = capture_network(page)

        prepare_ai_chapter(
            page,
            authed_request,
            sel_novel.novel_id,
            title="Extend Chapter",
            content=_EXTEND_SEED,
        )
        focus_editor_end(page)
        before = len(editor_text(page))
        assert before > 0

        page.get_by_role("button", name="Continue writing").click()

        page.wait_for_function(
            """(before) => (
                document.querySelector('.ProseMirror')?.innerText.length > before + 10
            )""",
            arg=before,
            timeout=60_000,
        )
        grown = editor_text(page)
        assert grown.startswith(_EXTEND_SEED.split(".")[0])  # append, not replace
        network.assert_no_provider_calls()


@pytest.mark.e2e
class TestRewrite:
    def test_rewrite_modal_preview_and_replace_applies_alternative(
        self, sel_novel: NovelContext, authed_request: Callable[..., http_requests.Response]
    ) -> None:
        """B01 pin: select text → AI rewrite → modal stays open with a
        preview → Replace swaps the selection (pre-fix: guaranteed 422 +
        silent modal close)."""
        page = sel_novel.page
        mock_llm(page, "rewrite_stream")  # happy variant

        prepare_ai_chapter(
            page,
            authed_request,
            sel_novel.novel_id,
            title="Rewrite Chapter",
            content=_EXTEND_SEED,
        )

        editor = page.locator(".ProseMirror").first
        editor.click()
        page.keyboard.press("Control+a")  # ~150-char selection < 2000 cap

        page.get_by_role("button", name="AI rewrite").click()
        page.get_by_text("Rewrite Selection").first.wait_for(state="visible", timeout=15_000)

        # Scoped to the mode-selector overlay on purpose: the toolbar's
        # generation toggle shares the accessible name "Generate" with the
        # modal footer button (same strict-mode collision class the
        # generation specs solve via click_panel_generate).
        mode_selector = page.locator("div.fixed.inset-0").filter(
            has=page.get_by_role("heading", name="Rewrite Selection")
        )
        mode_selector.get_by_role("button", name="Generate", exact=True).click()

        page.get_by_text("Tighter").first.wait_for(state="visible", timeout=30_000)

        # selectedSuggestion defaults to index 0 ("Tighter"); Replace applies
        # suggestions[selectedSuggestion] — select the second card so the
        # applied body is the "iron on iron" alternative the assertions pin.
        page.get_by_text("More sensory").first.click()

        page.get_by_role("button", name="Replace", exact=True).click()

        page.wait_for_function(
            """() => document.querySelector('.ProseMirror')?.innerText.includes('Tighter') === false
                && document.querySelector('.ProseMirror')?.innerText.includes('iron on iron')""",
            timeout=30_000,
        )
        # The alternative replaced the original selection.
        assert "iron on iron" in editor_text(page)
        assert "counted the strikes" not in editor_text(page)
