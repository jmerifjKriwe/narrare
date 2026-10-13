"""E2E test configuration and shared fixtures.

Playwright E2E tests run against the full stack (API + Frontend + PostgreSQL).
They are NOT part of the default test run — use: pytest tests/e2e/ -v -m e2e

All LLM responses are mocked via page.route() — no real API tokens are consumed.

KNOWN ISSUES / WORKAROUNDS:
- API calls through the Next.js proxy during browser page load can hang
  (concurrent fetch requests at +0.4s that include a POST with no body).
  Fixed: all authenticated_page fixtures use route.fetch() which bypasses
  the browser's network stack and avoids the hang.
- The first API database connection can take ~30s (asyncpg connection pool
  cold start). Fixed: warmup_api() fixture makes a health-check request
  before any test begins.
"""

from __future__ import annotations

import contextlib
import os
import uuid
from typing import TYPE_CHECKING, Any

import pytest
import requests as http_requests

from tests.e2e.config import API_URL, BASE_URL, DEV_EMAIL, DEV_PASSWORD

# Re-exported so pytest discovers the foundation fixtures for tests/e2e/
# specs. Defined in tests/e2e/foundation.py (RULE-04: conftest hard size
# limit) — the public fixture API is unchanged.
from tests.e2e.foundation import (  # noqa: F401 — re-export for fixture discovery
    _validate_mock_catalog,
    module_stable_user,
    stable_novel,
    stable_user,
    verify_e2e_environment,
)
from tests.e2e.http_session import build_api_session

if TYPE_CHECKING:
    from collections.abc import Generator

    from playwright.sync_api import Browser, Page


# ---------------------------------------------------------------------------
# Session-scoped warmup (cold-start database connection pool)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def warmup_api() -> None:
    """Make a warmup API request to initialize the database connection pool.

    The first API call after a cold start can take ~30s because asyncpg
    establishes its initial connection pool. This fixture runs automatically
    before any test, pre-warming the pool so test requests are fast.

    Uses contextlib.suppress per RULE-11: the warmup is advisory, not
    required — the health endpoint might not exist.
    """
    import contextlib

    # Non-blocking warmup — the health endpoint might not exist.
    # Using suppress per RULE-11: the warmup is advisory, not required.
    with contextlib.suppress(Exception):
        http_requests.get(f"{API_URL}/health", timeout=60)


# ---------------------------------------------------------------------------
# Screenshot-on-failure (replaces all manual page.screenshot() calls)
# ---------------------------------------------------------------------------

_SCREENSHOT_DIR = "test-results"


@pytest.fixture(autouse=True)
def screenshot_on_failure(request, page: Page) -> Generator[None]:
    """Automatically capture a screenshot when an E2E test fails.

    Replaces all manual ``page.screenshot()`` debug calls. Screenshots are
    saved to ``test-results/<test_name>.png`` and can be uploaded as CI
    artifacts.

    Uses ``contextlib.suppress`` per RULE-11: the screenshot is advisory —
    it must never raise and mask the original test failure.
    """
    yield
    if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
        test_name = request.node.nodeid.replace("::", "_").replace("/", "_")
        screenshot_path = os.path.join(_SCREENSHOT_DIR, f"{test_name}.png")
        with contextlib.suppress(Exception):
            os.makedirs(_SCREENSHOT_DIR, exist_ok=True)
            page.screenshot(path=screenshot_path)
            print(f"\n  [screenshot-on-failure] {screenshot_path}")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Store test result in item for screenshot_on_failure fixture."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


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
def api_session() -> http_requests.Session:
    """A ``requests.Session`` that mimics a browser for direct API calls.

    E2E tests make direct HTTP calls to the API (outside the browser) to
    seed data (``register_unique_user``) and drive state changes. The
    ``OriginValidationMiddleware`` (AUFG-05-13) rejects state-changing
    requests with no ``Origin`` / ``Referer`` / ``Bearer``. A real browser
    always sends an ``Origin`` header, so this session sets ``Origin`` /
    ``Referer`` to the frontend page origin (``BASE_URL``) by default —
    matching production behaviour instead of relying on CI's ``is_test``
    CSRF bypass.

    Per-call ``headers=`` (e.g. ``Authorization``) merge with these
    defaults, so ``Origin`` survives even when callers pass extra headers.
    """
    return build_api_session(BASE_URL)


@pytest.fixture(scope="session")
def browser_type_launch_args() -> dict[str, Any]:
    """Launch Chromium only. Headless in CI, headed locally for debugging."""
    return {
        "headless": os.environ.get("HEADED", "") != "true",
        "args": ["--disable-gpu", "--no-sandbox"],
    }


@pytest.fixture(scope="session")
def browser_context_args() -> dict[str, Any]:
    """Default context args — consistent viewport, locale."""
    return {
        "viewport": {"width": 1280, "height": 720},
        "locale": "en-US",
    }


@pytest.fixture(autouse=True)
def _skip_feature_tour(page: Page) -> Generator[None]:
    """Disable the feature tour for all E2E tests."""
    page.add_init_script("localStorage.setItem('narrare:featureTourCompleted', 'true');")
    yield


@pytest.fixture
def fresh_page(browser: Browser, browser_context_args: dict[str, Any]) -> Generator[Page]:
    """Clean browser context — no auth, fresh state."""
    context = browser.new_context(**browser_context_args)  # type: ignore[arg-type]
    page = context.new_page()
    page.add_init_script("localStorage.setItem('narrare:featureTourCompleted', 'true');")
    yield page
    context.close()


@pytest.fixture
def authenticated_page(browser: Browser, browser_context_args: dict[str, Any]) -> Generator[Page]:
    """Browser page with a valid JWT session via the dev user.

    Logs in via the API, then uses page.route() to:
    1. Add the Authorization header to all API requests
    2. Proxy via route.fetch() (Playwright's network) to avoid browser
       connection pool hangs during page load.

    The narrare_auth cookie is also set so Next.js middleware (server-side
    route protection) works correctly.
    """
    context = browser.new_context(**browser_context_args)  # type: ignore[arg-type]
    page = context.new_page()
    page.add_init_script("localStorage.setItem('narrare:featureTourCompleted', 'true');")

    # -----------------------------------------------------------------------
    # Step 1: Log in via the API (direct HTTP, not through the browser).
    # Send a browser-like Origin header so the request survives the CSRF
    # OriginValidationMiddleware even when CI's is_test bypass is off.
    # -----------------------------------------------------------------------
    login_response = page.request.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"email": DEV_EMAIL, "password": DEV_PASSWORD},
        headers={"Origin": BASE_URL},
    )

    if login_response.status == 429:
        pytest.skip("Rate limited — retry later")

    assert login_response.status == 200, (
        f"Login failed with status {login_response.status}: {login_response.text()}"
    )

    tokens = login_response.json()
    access_token = tokens["access_token"]

    # -----------------------------------------------------------------------
    # Step 2: Set up route handlers BEFORE any page navigation.
    # This is critical — the route handler must intercept API requests
    # from the very first page load, not just subsequent navigations.
    # -----------------------------------------------------------------------

    # Set the narrare_auth cookie so Next.js middleware (server-side route
    # protection) works on the initial page load.
    # We embed the token directly in the script string because
    # add_init_script does not accept runtime arguments.
    page.add_init_script(
        f"""document.cookie = 'narrare_auth={access_token}; path=/; max-age=3600; samesite=lax';"""
    )

    def _proxy_with_auth(route):
        """Intercept API requests: add auth header, proxy via Playwright network.

        Uses route.fetch() (Playwright's HTTP client) instead of
        route.continue_() to avoid the browser connection-pool hang
        that occurs when the app fires fetch requests concurrently at
        +0.4s during page load.
        """
        headers = dict(route.request.headers)
        # Add the auth header if not already present
        if "authorization" not in {k.lower() for k in headers}:
            headers["Authorization"] = f"Bearer {access_token}"
        try:
            response = route.fetch(headers=headers)
            route.fulfill(
                status=response.status,
                headers=response.headers,
                body=response.body(),
            )
        except Exception:
            route.continue_(headers=headers)

    page.route("**/api/v1/**", _proxy_with_auth)

    # -----------------------------------------------------------------------
    # Step 3: Now navigate to the app. The route handler is already active,
    # so the initial fetch requests will be intercepted and proxied via
    # Playwright's network stack (no browser connection-pool hang).
    # -----------------------------------------------------------------------
    page.goto(BASE_URL)

    # Wait for the auth store to initialize (loadUser completes)
    page.wait_for_timeout(1000)

    yield page
    context.close()


@pytest.fixture
def api_request(api_session: http_requests.Session, api_url: str):
    """Provide a helper to make direct API requests via the shared browser-mimic session.

    Returns a callable: ``api_request(method, path, **kwargs) -> Response``.
    The session sets ``Origin`` / ``Referer`` by default so CSRF validation
    passes on state-changing methods.
    """

    def _request(method: str, path: str, **kwargs) -> http_requests.Response:
        """Make an API request. path is relative to api_url (e.g. /api/v1/auth/login)."""
        url = f"{api_url}{path}"
        return api_session.request(method, url, **kwargs)

    return _request


@pytest.fixture
def register_unique_user(api_session: http_requests.Session, api_url: str):
    """Register a unique test user and return credentials + token.

    Uses the shared ``api_session`` (browser-mimic ``Origin`` / ``Referer``)
    so the CSRF ``OriginValidationMiddleware`` accepts the registration POST
    outside CI's ``is_test`` bypass.

    Returns dict with: email, password, access_token, refresh_token
    """

    def _register() -> dict[str, str]:
        email = f"e2e-{uuid.uuid4().hex[:8]}@example.com"
        password = "E2eTest123!pass"
        resp = api_session.post(
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
