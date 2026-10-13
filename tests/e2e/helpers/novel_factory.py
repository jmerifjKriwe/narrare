"""Novel factory: wizard completion + volume/chapter API setup (spec §4).

``complete_wizard`` drives the CURRENT 5-step wizard (WizardShell.tsx):
1 project name + language · 2 starter selection (blank/import/demo cards,
   ``button[aria-pressed]`` in render order) · 3 novel details
   (``#novel_title``) · 4 provider (LLM-mocked, Next disabled until a model
   auto-selects) · 5 complete → editor redirect.

The page must ALREADY be logged in (compose with audit_user helpers or the
conftest stable_* fixtures) — the factory owns no auth concerns (RULE-04).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from tests.e2e.mocks.llm_responses import setup_llm_mocks
from tests.e2e.test_helpers import _click_next, _wait_for_wizard_ready

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import requests
    from playwright.sync_api import Page

STARTER_BLANK = "blank"
STARTER_IMPORT = "import"
STARTER_DEMO_FANTASY = "demo_fantasy"
STARTER_DEMO_SCIFI = "demo_scifi"
STARTER_DEMO_GERMAN = "demo_german"

# StarterCard render order in WizardStep2.tsx (blank, import, then DEMO_OPTIONS).
_STARTER_CARD_INDEX = {
    STARTER_BLANK: 0,
    STARTER_IMPORT: 1,
    STARTER_DEMO_FANTASY: 2,
    STARTER_DEMO_SCIFI: 3,
    STARTER_DEMO_GERMAN: 4,
}

# Wizard wait budgets (RULE-18: named, not call-site literals).
_STEP_TIMEOUT_MS: int = 10_000  # step transitions + element visibility
_REDIRECT_TIMEOUT_MS: int = 15_000  # step-4 model auto-select + editor redirect


def complete_wizard(
    page: Page,
    base_url: str,
    *,
    starter: str = STARTER_BLANK,
    novel_title: str = "Factory Novel",
    import_file: Path | None = None,
) -> dict[str, str]:
    """Complete the setup wizard on a logged-in page → ``{"novel_id": …}``."""
    if starter not in _STARTER_CARD_INDEX:
        raise ValueError(f"Unknown starter {starter!r}; known: {sorted(_STARTER_CARD_INDEX)}")
    if starter == STARTER_IMPORT and import_file is None:
        raise ValueError("starter='import' requires import_file=")

    setup_llm_mocks(page)  # provider validation + model listing (step 4)

    page.goto(f"{base_url}/wizard")
    _wait_for_wizard_ready(page)

    # Step 1: project name (+ language default en).
    project_name_input = page.locator(
        'input[name="project_name"], input[id="project_name"], input[placeholder*="project" i]'
    ).first
    if project_name_input.is_visible():
        project_name_input.fill(novel_title)
    _click_next(page, expected_step=2)

    # Step 2: starter card selection (positional among aria-pressed cards).
    cards = page.locator("button[aria-pressed]")
    cards.wait_for(state="visible", timeout=_STEP_TIMEOUT_MS)
    card = cards.nth(_STARTER_CARD_INDEX[starter])
    card.click()
    page.wait_for_function(
        """(index) => {
            const card = document.querySelectorAll('button[aria-pressed]')[index];
            return card && card.getAttribute('aria-pressed') === 'true';
        }""",
        arg=_STARTER_CARD_INDEX[starter],
        timeout=_STEP_TIMEOUT_MS,
    )
    if starter == STARTER_IMPORT:
        page.locator('[data-testid="wizard-import-section"]').wait_for(
            state="visible", timeout=_STEP_TIMEOUT_MS
        )
        page.set_input_files("#import-file-input", str(import_file))
        page.wait_for_timeout(500)  # client-side parse + onSelectionChange
    _click_next(page, expected_step=3)

    # Step 3: novel details — fill title ONLY when not prefilled (N17-neutral).
    title_input = page.locator("#novel_title").first
    title_input.wait_for(state="visible", timeout=_STEP_TIMEOUT_MS)
    if not title_input.input_value():
        title_input.fill(novel_title)
    _click_next(page, expected_step=4)

    # Step 4: provider (mocked) — wait until Next is enabled (model selected).
    page.wait_for_function(
        "document.querySelector('[data-testid=\"wizard-next\"]')"
        " && !document.querySelector('[data-testid=\"wizard-next\"]').disabled",
        timeout=_REDIRECT_TIMEOUT_MS,
    )
    _click_next(page)

    # Step 5: complete → editor redirect.
    page.locator('[data-testid="wizard-complete"]').first.wait_for(
        state="visible", timeout=_REDIRECT_TIMEOUT_MS
    )
    page.locator('[data-testid="wizard-complete"]').first.click()
    page.wait_for_url(
        lambda url: "/novel/" in url or "/dashboard" in url, timeout=_REDIRECT_TIMEOUT_MS
    )
    if "/novel/" not in page.url:
        page.wait_for_timeout(1_000)
        novel_link = page.locator('a[href*="/novel/"]').first
        novel_link.click()
        page.wait_for_url(lambda url: "/novel/" in url, timeout=_REDIRECT_TIMEOUT_MS)

    match = re.search(r"/novel/([a-f0-9-]+)", page.url)
    if not match:
        raise ValueError(f"No novel ID found in URL: {page.url}")
    return {"novel_id": match.group(1)}


def create_volume_via_api(
    api_request: Callable[..., requests.Response],
    novel_id: str,
    *,
    title: str = "Act I",
    subtitle: str | None = None,
    description: str | None = None,
) -> dict:
    """Create a volume via the API (CreateVolumeRequest contract)."""
    resp = api_request(
        "POST",
        f"/api/v1/novels/{novel_id}/volumes",
        json={"title": title, "subtitle": subtitle, "description": description},
    )
    assert resp.status_code == 201, f"Volume create failed: {resp.status_code} {resp.text[:300]}"
    return resp.json()


def create_chapter_via_api(
    api_request: Callable[..., requests.Response],
    novel_id: str,
    *,
    title: str = "New Chapter",
    content: str = "",
    volume_id: str | None = None,
) -> dict:
    """Create a chapter via the API (CreateChapterRequest contract)."""
    body: dict[str, object] = {"title": title, "content": content}
    if volume_id is not None:
        body["volume_id"] = volume_id
    resp = api_request("POST", f"/api/v1/novels/{novel_id}/chapters", json=body)
    assert resp.status_code == 201, f"Chapter create failed: {resp.status_code} {resp.text[:300]}"
    return resp.json()
