"""Canned LLM responses and Playwright route handlers for E2E tests.

All LLM provider responses are mocked via Playwright's page.route() API.
No real LLM API calls are made during E2E test execution.

Usage in tests:
    from tests.e2e.mocks.llm_responses import setup_llm_mocks

    def test_something(page):
        setup_llm_mocks(page)
        # Now all LLM-related API calls return canned responses
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page, Route


# ---------------------------------------------------------------------------
# Canned responses
# ---------------------------------------------------------------------------

PROVIDER_VALIDATION_SUCCESS = {
    "valid": True,
    "provider": "openai",
    "model": "gpt-4o-mini",
    "validation_message": "Connection verified successfully",
}

PROVIDER_MODELS_RESPONSE = {
    "provider": "openai",
    "models": [
        {
            "id": "gpt-4o-mini",
            "name": "GPT-4o Mini",
            "context_window": 128000,
            "supports_streaming": True,
        },
        {
            "id": "gpt-4o",
            "name": "GPT-4o",
            "context_window": 128000,
            "supports_streaming": True,
        },
    ],
}


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def _handle_provider_validation(route: Route) -> None:
    """Mock the setup wizard step 4 provider validation endpoint."""
    route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(PROVIDER_VALIDATION_SUCCESS),
    )


def _handle_provider_models(route: Route) -> None:
    """Mock the provider models listing endpoint."""
    route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(PROVIDER_MODELS_RESPONSE),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def setup_llm_mocks(page: Page, *, base_url: str = "http://localhost:3000") -> None:
    """Install Playwright route interceptors for all LLM-related API calls.

    This ensures NO real LLM API requests are made during E2E tests.
    Intercepts:
      - POST /api/v1/setup/validate/step-4 (provider validation)
      - GET /api/v1/setup/providers/*/models (model listing)

    Args:
        page: Playwright page object to install routes on.
        base_url: The frontend base URL (for route matching).
    """
    # Mock provider validation (step 4) — the endpoint that tests the API key
    page.route("**/api/v1/setup/validate/step-4", _handle_provider_validation)

    # Mock provider model listing
    page.route("**/api/v1/setup/providers/*/models**", _handle_provider_models)
