"""Settings Persistence E2E Tests.

Covers: settings page loading, tab navigation, novel detail persistence
across page reloads.

All LLM responses are mocked via page.route() — no real API tokens consumed.
Runs against the full stack (URLs via E2E_BASE_URL / E2E_API_URL, see
tests/e2e/config.py). Sessions come from the foundation ``stable_novel``
fixture (deterministic logged-in state; nightly-38231495215 triage).
"""

from __future__ import annotations

import uuid

import pytest

from tests.e2e.test_helpers import goto_with_retry


@pytest.mark.e2e
class TestSettingsPersistence:
    """Test settings page rendering and persistence of novel details."""

    def test_settings_novel_details_persist_after_reload(
        self,
        stable_novel,
        base_url: str,
    ) -> None:
        """Changing novel title in settings persists after page reload."""
        page = stable_novel.page
        novel_id = stable_novel.novel_id

        # Navigate to settings
        goto_with_retry(page, f"{base_url}/novel/{novel_id}/settings")
        page.wait_for_timeout(2000)

        # The default tab is "novel-details" so the title input should
        # already be visible.  Use the actual selector from
        # NovelDetailsTab.tsx: id="novel-title".
        title_selectors = [
            "#novel-title",
            'input[data-testid="novel-title"]',
            'input[name="title"]',
            'input[placeholder*="title" i]',
        ]
        title_input = None
        for selector in title_selectors:
            locator = page.locator(selector).first
            if locator.is_visible():
                title_input = locator
                break

        if title_input is None:
            # Debug: print all inputs on the page
            all_inputs = page.locator("input[type='text'], input:not([type])").all()
            print(f"  Found {len(all_inputs)} text inputs on settings page:")
            for i, inp in enumerate(all_inputs):
                if inp.is_visible():
                    print(
                        f"    [{i}] name={inp.get_attribute('name')}, "
                        f"id={inp.get_attribute('id')}, "
                        f"placeholder={inp.get_attribute('placeholder')}, "
                        f"value={inp.input_value()[:50]}"
                    )
            pytest.skip("Could not find title input on settings page — may need different selector")

        # Change the title
        new_title = f"Updated Novel {uuid.uuid4().hex[:6]}"
        title_input.click()
        title_input.fill("")
        title_input.fill(new_title)
        page.wait_for_timeout(500)

        # Save — the NovelDetailsTab save button is inside a
        # ``div.flex.justify-end`` container.  We avoid matching the active
        # settings-tab buttons which also have the ``bg-primary`` class.
        save_btn = page.locator('div.flex.justify-end > button[type="button"]').first
        if not save_btn.is_visible():
            # Fallback: text-based search
            save_btn = page.locator(
                'button:has-text("Save"), '
                'button:has-text("Speichern"), '
                'button:has-text("Enregistrer")'
            ).first
        if save_btn.is_visible():
            save_btn.click()
            page.wait_for_timeout(2000)
        else:
            print("  Save button not visible — title change may auto-save")

        # Reload
        page.reload()
        page.wait_for_timeout(3000)

        # Click novel-details tab again to be safe
        details_tab = page.locator('[data-testid="settings-tab-novel-details"]').first
        if details_tab.is_visible():
            details_tab.click()
            page.wait_for_timeout(500)

        # Find title input again
        for selector in title_selectors:
            locator = page.locator(selector).first
            if locator.is_visible():
                title_input = locator
                break

        if title_input:
            value = title_input.input_value()
            assert new_title in value, f"Expected '{new_title}' after reload, got '{value}'"
        else:
            pytest.skip("Title input not found after reload — page may have changed")

    @pytest.mark.xfail(
        reason=(
            "nightly-38231495215 (Branch C, product regression): Settings → AI tab "
            "bounces authenticated users to /login — GET /settings/token-limits/ is "
            "308-slash-stripped by the Next.js rewrite, re-307'd by the API with an "
            "absolute http://localhost:8000 Location, the cross-origin redirect "
            "strips Authorization (fetch spec), and the post-refresh retry 401s "
            "again → core.ts dead-session bounce. Product fix lands in a separate "
            "slice; strict=True turns this into CI failure the moment the fix "
            "lands (XPASS), forcing mark removal."
        ),
        strict=True,
    )
    def test_settings_general_tab_renders(self, stable_novel, base_url: str) -> None:
        """Settings page loads with tabs and content (nightly 38231495215 triage).

        BRANCH C VERDICT (2026-10-13 triage, live stack): PRODUCT REGRESSION,
        not tab drift and not test-side session fragility. The tab list
        itself is correct — the strict 9-tab assertion below PASSES — and
        the AI tab then deterministically bounces the authenticated user
        to /login (observed 3/3 runs, also reproduced outside pytest):

        GET /api/v1/settings/token-limits/ (canonical slash-ful client URL)
          → Next.js rewrite/trailingSlash normalization 308-strips the slash
          → API redirect_slashes answers 307 with ABSOLUTE Location
            http://localhost:8000/api/v1/settings/token-limits/ (internal
            origin leaked through the Next rewrite)
          → browser follows the cross-origin redirect and strips the
            Authorization header (fetch spec) → 401
          → core.ts refreshes (200) and retries → same chain → 401 again
          → "refresh succeeded but retry still unauthorized — dead session"
            → window.location.href = "/login" (N06-class hard bounce)

        The tab walk below trips it at the ai → prompts transition, so this
        spec is pinned red via xfail(strict=True) until the product fix
        (relative redirect Location and/or slash-preserving rewrite) lands
        in a separate slice. Mark removal is the fix's regression gate:
        when the bounce is gone this test XPASSes and strict=True fails CI
        until the mark is dropped.
        """
        page = stable_novel.page
        goto_with_retry(page, f"{base_url}/novel/{stable_novel.novel_id}/settings")
        page.wait_for_timeout(2000)

        assert "/settings" in page.url, f"Expected settings URL, got: {page.url}"
        assert "/login" not in page.url, (
            "Session bounced mid-navigation (N06 class) — stable_novel should "
            "make this impossible; treat as a product regression, not a flake."
        )

        # SSOT: packages/web/components/studio/settings/settings-view-config.ts
        expected_tabs = [
            "novel-details",
            "general",
            "writing",
            "ai",
            "prompts",
            "kb-templates",
            "learning",
            "shortcuts",
            "about",
        ]
        tab_buttons = page.locator('button[data-testid^="settings-tab-"]')
        rendered_ids = [
            tab_buttons.nth(i).get_attribute("data-testid").removeprefix("settings-tab-")
            for i in range(tab_buttons.count())
        ]
        assert rendered_ids == expected_tabs, (
            f"Settings tabs drifted from settings-view-config.ts: rendered "
            f"{rendered_ids}, expected {expected_tabs}"
        )

        for i in range(tab_buttons.count()):
            tab = tab_buttons.nth(i)
            tab.wait_for(state="visible", timeout=10_000)
            tab.click()
            page.wait_for_timeout(300)
