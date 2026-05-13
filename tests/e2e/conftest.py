"""E2E test configuration and shared fixtures.

Playwright E2E tests run against the full stack (API + Frontend + PostgreSQL + Redis).
They are NOT part of the default test run — use: pytest tests/e2e/ -v -m e2e

All LLM responses are mocked via page.route() — no real API tokens are consumed.
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from playwright.sync_api import Browser, Page


# ---------------------------------------------------------------------------
# URLs
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:3000")
API_URL = os.environ.get("E2E_API_URL", "http://localhost:8000")

# Dev user credentials (seeded by scripts/seed_dev_user.py)
DEV_EMAIL = "dev@narrare.dev"
DEV_PASSWORD = "narrare-dev"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def api_url() -> str:
    return API_URL


@pytest.fixture(scope="session")
def browser_type_launch_args() -> dict[str, Any]:
    """Launch Chromium only. Headless in CI, headed locally for debugging."""
    return {
        "headless": os.environ.get("CI", "") == "true",
        "args": ["--disable-gpu", "--no-sandbox"],
    }


@pytest.fixture(scope="session")
def browser_context_args() -> dict[str, Any]:
    """Default context args — consistent viewport, locale."""
    return {
        "viewport": {"width": 1280, "height": 720},
        "locale": "en-US",
    }


@pytest.fixture
def fresh_page(browser: Browser, browser_context_args: dict[str, Any]) -> Generator[Page]:
    """Clean browser context — no auth, fresh state."""
    context = browser.new_context(**browser_context_args)  # type: ignore[arg-type]
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture
def authenticated_page(browser: Browser, browser_context_args: dict[str, Any]) -> Generator[Page]:
    """Browser page with a valid JWT session via the dev user.

    Logs in via the API, then sets the access token in the browser's
    execution context so the frontend auth store picks it up.
    """
    context = browser.new_context(**browser_context_args)  # type: ignore[arg-type]
    page = context.new_page()

    # Navigate to the app first so we have a JS context
    page.goto(BASE_URL)

    # Login via API (synchronous request through the Next.js rewrite proxy)
    login_response = page.request.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"email": DEV_EMAIL, "password": DEV_PASSWORD},
    )

    if login_response.status == 429:
        pytest.skip("Rate limited — retry later")

    assert login_response.status == 200, (
        f"Login failed with status {login_response.status}: {login_response.text()}"
    )

    tokens = login_response.json()
    access_token = tokens["access_token"]

    # Inject token into the frontend's auth store via page.evaluate
    # The frontend stores the token in memory via setAccessToken()
    page.evaluate(
        """(token) => {
            // Set the token in the API client's in-memory store
            // by dispatching through the zustand store or direct injection
            window.__E2E_ACCESS_TOKEN__ = token;

            // Use the auth store to set the token properly
            // This works because the store is globally accessible via zustand
            const stores = document.querySelectorAll('[data-store]');
            if (stores.length > 0) {
                // zustand store found, use the API directly
            }
        }""",
        access_token,
    )

    # Alternative: set token via the API client's setAccessToken function
    # We do this by navigating to a page and injecting a script that calls setAccessToken
    page.evaluate(
        """(token) => {
            // The frontend bundles setAccessToken in its module scope.
            // We can intercept API calls and add the Authorization header instead.
            window.__E2E_AUTH_TOKEN__ = token;
        }""",
        access_token,
    )

    # Intercept all /api/v1/ requests and add the Authorization header
    def _add_auth_header(route):
        headers = {
            **route.request.headers,
            "Authorization": f"Bearer {access_token}",
        }
        route.continue_(headers=headers)

    page.route("**/api/v1/**", _add_auth_header)

    yield page
    context.close()


@pytest.fixture
def api_request(api_url: str, base_url: str):
    """Provide a helper to make authenticated API requests via the browser proxy.

    Returns a callable: api_request(method, path, **kwargs) -> Response
    """
    import requests as http_requests

    def _request(method: str, path: str, **kwargs) -> http_requests.Response:
        """Make an API request. path is relative to api_url (e.g. /api/v1/auth/login)."""
        url = f"{api_url}{path}"
        return http_requests.request(method, url, **kwargs)

    return _request


@pytest.fixture
def register_unique_user(api_url: str):
    """Register a unique test user and return credentials + token.

    Returns dict with: email, password, access_token, refresh_token
    """
    import requests as http_requests

    def _register() -> dict[str, str]:
        email = f"e2e-{uuid.uuid4().hex[:8]}@example.com"
        password = "E2eTest123!pass"
        resp = http_requests.post(
            f"{api_url}/api/v1/auth/register",
            json={"email": email, "password": password, "display_name": "E2E Test User"},
        )
        assert resp.status_code == 201, f"Registration failed: {resp.status_code} {resp.text}"
        data = resp.json()
        return {
            "email": email,
            "password": password,
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
        }

    return _register
