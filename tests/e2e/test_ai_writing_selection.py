"""AI-writing E2E specs — selection tools: extend, rewrite, co-author, unblock.

WRITE-003 extend (B08 pin: toolbar wiring), WRITE-004 rewrite (B01 pin:
500-char context compliance, modal/preview reachable, Replace applies),
WRITE-006 co-author real happy path + B09 slash wiring pin, WRITE-009
unblock suggestions (B02 pin: novel_id in the body → suggestions render +
insert). Extend runs on the TestModel factory layer (tolerance-loose,
spec §3); rewrite and co-author are deterministic via the browser-layer
catalog (FE parses ``<alternative>`` tags — TestModel output would be junk
for Apply paths; the co-author catalog pattern deliberately ends at
``/co-author``, so the all-accepted apply is the client-side path).

Entry-point note (Task 4 carry-over): the rewrite flow and the co-author
happy path drive the REAL bubble menu (the "AI rewrite" and "Co-Author"
buttons live in TipTapBubbleMenu, shown on a live selection). TestCoAuthor
pins Task 4's ``onCoAuthor`` branch (selection → overlay). The slash
trigger provably cannot carry a selection (Decisions log D-2026-10-13-1),
so the slash spec pins the availability gate instead: the no-selection
item renders disabled with actionable guidance and dispatching is a
guarded no-op (no overlay).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.e2e.config import BASE_URL
from tests.e2e.foundation import NovelContext, make_authed_request
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

    Delegates to the foundation factory (extracted at the Task 9 third
    consumer; this module held the second copy).
    """
    return make_authed_request(api_request, sel_novel)


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


@pytest.mark.e2e
class TestUnblock:
    def test_unblock_suggestions_render_and_insert(
        self, sel_novel: NovelContext, authed_request: Callable[..., http_requests.Response]
    ) -> None:
        """B02 pin: the panel fetches suggestions (novel_id in the body —
        pre-fix 422 'Field required') and Accept inserts into the editor."""
        page = sel_novel.page
        network = capture_network(page)
        mock_llm(page, "story_suggest")  # happy variant

        prepare_ai_chapter(page, authed_request, sel_novel.novel_id, title="Unblock Chapter")
        focus_editor_end(page)

        page.get_by_role("button", name="Writer's Unblock").click()
        page.get_by_text("Get Suggestions").wait_for(state="visible", timeout=15_000)

        # The textarea carries no placeholder (UnblockInputForm) — it is
        # labelled "Stuck?" (unblock.stuckLabel, htmlFor="unblock-stuck").
        page.get_by_label("Stuck?").fill("The gate scene has no way forward.")
        page.get_by_role("button", name="Get Suggestions").click()

        first_card = page.get_by_text("The writ names a rival house").first
        first_card.wait_for(state="visible", timeout=30_000)

        # Insert the first suggestion at the caret (aiActions.accept on the card).
        page.get_by_role("button", name="Accept", exact=True).first.click()

        page.wait_for_function(
            "() => document.querySelector('.ProseMirror')?.innerText.includes('rival house')",
            timeout=30_000,
        )
        assert "rival house" in editor_text(page)
        network.assert_no_provider_calls()


@pytest.mark.e2e
class TestCoAuthor:
    def test_slash_menu_lists_coauthor_as_wired_command(
        self, sel_novel: NovelContext, authed_request: Callable[..., http_requests.Response]
    ) -> None:
        """B09 wiring pin: the slash menu offers Co-Author as a real command
        (pre-fix: stub 'Not available here'), and the no-selection guard is
        an actionable no-op (availability gating)."""
        page = sel_novel.page
        network = capture_network(page)

        prepare_ai_chapter(page, authed_request, sel_novel.novel_id, title="CoAuthor Slash")
        editor = page.locator(".ProseMirror").first
        editor.click()
        page.keyboard.press("Control+End")
        page.keyboard.press("Enter")  # fresh empty paragraph
        page.keyboard.type("/")

        page.get_by_text("Co-Author", exact=True).first.wait_for(state="visible", timeout=15_000)

        # Availability gate: the handler IS wired (no stub), but without a
        # selection the item renders disabled with actionable guidance.
        coauthor_item = page.locator(".slash-command-menu button").filter(has_text="Co-Author")
        assert coauthor_item.first.get_attribute("disabled") is not None
        assert "Select text first" in coauthor_item.first.inner_text()

        # Without a selection the command must not dispatch (guarded no-op).
        # A real pointer click cannot fire at all — the browser suppresses
        # clicks on the disabled control (Playwright actionability would wait
        # forever) — so drive the menu item's own guard branch directly:
        # dispatch_event bubbles a synthetic click to the button, whose
        # onClick checks `if (!disabled)` and no-ops.
        page.get_by_text("Co-Author", exact=True).first.dispatch_event("click")
        page.wait_for_timeout(500)
        assert (
            page.get_by_text("Co-Author", exact=True).count() == 0
            or not page.locator(".fixed.inset-0").count()
        ), "no-selection dispatch must not open the overlay"
        network.assert_no_provider_calls()

    def test_selected_passage_bubble_entry_full_coauthor_flow(
        self, sel_novel: NovelContext, authed_request: Callable[..., http_requests.Response]
    ) -> None:
        """WRITE-006 real happy path (PO ruling 1; fix = Task 4's bubble
        entry): select a passage → bubble Co-Author → overlay carries the
        passage → Start → streamed revision with structured changes →
        apply replaces the selection in the editor. No xfail — fixed path."""
        page = sel_novel.page
        network = capture_network(page)
        mock_llm(page, "coauthor_stream")  # happy variant (Task 6)

        prepare_ai_chapter(
            page, authed_request, sel_novel.novel_id, title="CoAuthor Happy", content=_EXTEND_SEED
        )
        editor = page.locator(".ProseMirror").first
        editor.click()
        page.keyboard.press("Control+a")

        # Task 4's selection-carrying trigger (the slash trigger provably
        # cannot carry one — Decisions log D-2026-10-13-1).
        page.get_by_role("button", name="Co-Author", exact=True).first.click()

        # The overlay opens in the focus phase carrying the passage.
        overlay = page.locator(".fixed.inset-0").first
        overlay.wait_for(state="visible", timeout=15_000)
        assert "30 words selected" in overlay.inner_text(), (
            "the overlay must open carrying the selected passage "
            "(calibrate the count on :3001 if the doc model shifts a word boundary)"
        )

        page.get_by_role("button", name="Start", exact=True).click()

        # Review phase: the final event's structured changes render as a diff
        # ("counted the strikes" → "counted each strike", Task 6 fixture).
        page.get_by_text("1 improvements found").first.wait_for(state="visible", timeout=30_000)
        # AIDiffSegmentList renders the revision as accessible <ins>/<del>
        # segments — markers and sr-only labels interleave the words, so the
        # revised wording arrives as the ins segment ("each"), not one
        # contiguous innerText substring.
        overlay.locator("ins").filter(has_text="each").first.wait_for(
            state="visible", timeout=15_000
        )

        # Apply with all changes accepted (the panel default). Deliberately
        # the all-accepted path: it applies client-side (onAccept), while a
        # partial apply would POST the REAL /co-author/apply with the mock's
        # request_id and correctly fail (see the task's apply-path note).
        # Two "Accept All" buttons exist (header chip + primary apply) —
        # .last is the primary apply button.
        page.get_by_role("button", name="Accept All").last.click()

        # The EditorView host closes the overlay synchronously on accept:
        # flow.accept (useEditorAiEntryPoints) sets the selection null in the
        # same tick as the panel's setPhase("done") (useCoAuthorApply), so
        # React batches both and the done phase never paints in this wiring
        # (verified live — the panel vanishes; "Changes applied successfully"
        # only renders on hosts that stay mounted through onAccept).
        overlay.wait_for(state="detached", timeout=15_000)

        # The streamed revision replaced the selected passage in the editor.
        assert "tasting salt on the wind" in editor_text(page)
        assert "the way her mother" not in editor_text(page), (
            "the original passage must be replaced, not appended"
        )
        network.assert_no_provider_calls()
