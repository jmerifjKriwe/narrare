"""Foundation: environment fail-fast checks (spec §8) + shared stable fixtures.

Extracted from ``tests/e2e/conftest.py`` (RULE-04: the conftest hard size
limit) — the fixtures are re-exported by the conftest so pytest discovers
them for ``tests/e2e/`` specs. One responsibility per module (RULE-06):

- ``verify_e2e_environment`` — session fail-fast on the audit's environment
  couplings: E04/spec §3 TestModel banner + E01 proxy probe.
- ``_validate_mock_catalog`` — spec §10 drift ratchet at session start.
- ``stable_user`` / ``module_stable_user`` / ``stable_novel`` — the suite's
  deterministic session fixtures (PO ruling 2026-10-13: registration ONLY
  through the real /register form via ``audit_user.build_stable_session``).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import requests as http_requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.e2e.config import API_URL, BASE_URL, DEV_EMAIL, DEV_PASSWORD
from tests.e2e.helpers.novel_factory import complete_wizard

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from playwright.sync_api import Browser

# Setup-path transient tolerance (absorb ONCE, then fail loudly — RULE-11;
# the goto_with_retry contract from commit 168945f4 applied at fixture
# granularity).
_TRANSIENT_ATTEMPTS: int = 2
_TRANSIENT_BACKOFF_S: float = 2.0


def _send_with_retry(
    session: http_requests.Session, method: str, url: str, **kwargs: Any
) -> http_requests.Response:
    """Session-start HTTP with ONE retry on transient transport errors.

    Forensic target (Oct-15 nightly, run 38700481557): a mid-run API
    restart plus Next-proxy ``read ECONNRESET`` on ``/auth/refresh`` turned
    fixture setups into session-level errors. The retry absorbs only that
    transient window (connection reset / timeout); after the final attempt
    the original exception re-raises — real breakage is never masked.
    """
    for attempt in range(1, _TRANSIENT_ATTEMPTS + 1):
        try:
            return session.request(method, url, **kwargs)
        except http_requests.exceptions.RequestException:
            if attempt == _TRANSIENT_ATTEMPTS:
                raise
            time.sleep(_TRANSIENT_BACKOFF_S)
    raise AssertionError("unreachable")  # for pyright: loop always returns or raises


def _api_log_banner_present() -> bool | None:
    """True/False if logs/e2e-api.log exists; None when the log is absent
    (manual runs without the runner) — advisory only in that case (RULE-11)."""
    log_path = Path("logs/e2e-api.log")
    if not log_path.exists():
        return None
    return "e2e_test_mode_active" in log_path.read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="session", autouse=True)
def verify_e2e_environment(api_session: http_requests.Session) -> None:
    """Fail the whole session fast on the audit's environment couplings.

    - E04/spec §3: the API must run under NARRARE_E2E_TEST=1 (TestModel
      banner ``e2e_test_mode_active`` in logs/e2e-api.log). Skipped with a
      note when the log is absent (manual stack starts).
    - E01: the Next.js proxy must accept the API-issued narrare_auth cookie
      (requests-level probe — no browser needed).
    """
    banner = _api_log_banner_present()
    if banner is None:
        print("\n  [e2e-env] NOTE: logs/e2e-api.log absent — TestModel banner not verified")
    else:
        assert banner, (
            "NARRARE_E2E_TEST banner (e2e_test_mode_active) missing from "
            "logs/e2e-api.log — the API is making REAL LLM calls (spec §3). "
            "Restart the stack via scripts/run_e2e.sh."
        )

    login = _send_with_retry(
        api_session,
        "POST",
        f"{API_URL}/api/v1/auth/login",
        json={"email": DEV_EMAIL, "password": DEV_PASSWORD},
    )
    if login.status_code == 429:
        pytest.skip("Rate limited — retry later")
    assert login.status_code == 200, (
        f"Dev-user login failed: {login.status_code} {login.text[:300]}"
    )
    access_token = login.json()["access_token"]

    probe = _send_with_retry(
        api_session,
        "GET",
        f"{BASE_URL}/dashboard",
        cookies={"narrare_auth": access_token},
        allow_redirects=False,
    )
    location = probe.headers.get("location", "")
    bounced = probe.status_code >= 300 and probe.status_code < 400 and "/login" in location
    assert not bounced, (
        "E01: proxy redirected /dashboard → /login with a valid narrare_auth "
        "cookie. AUTH_JWT_SECRET is not exported to the web process or does "
        "not match the API's signing key (see scripts/run_e2e.sh env block)."
    )


@pytest.fixture(scope="session", autouse=True)
def _validate_mock_catalog() -> None:
    """Spec §10: every catalog entry validates against the real models."""
    from tests.e2e.mocks.catalog import validate_catalog

    validate_catalog()


@dataclass
class StableUser:
    """Fresh unique user with a deterministic logged-in page session."""

    page: Any
    email: str
    password: str
    access_token: str


@dataclass
class NovelContext:
    """StableUser plus a wizard-created novel open in the editor."""

    page: Any
    novel_id: str
    email: str
    password: str
    access_token: str


def make_authed_request(
    api_request: Callable[..., http_requests.Response],
    context: NovelContext,
) -> Callable[..., http_requests.Response]:
    """``api_request`` carrying a novel owner's bearer token (suite convention).

    The conftest ``api_request`` is deliberately unauthenticated (shared
    session); chapter seeding must land on THIS user's novel. Extracted once
    at the third consumer (Task 9) — previously module-local in
    ``test_ai_writing.py`` and ``test_ai_writing_selection.py``. Spec modules
    keep a two-line ``authed_request`` fixture binding their own novel fixture
    (the module novel fixture names differ by design).
    """

    def _request(method: str, path: str, **kwargs: object) -> http_requests.Response:
        return api_request(
            method,
            path,
            headers={"Authorization": f"Bearer {context.access_token}"},
            **kwargs,
        )

    return _request


def _new_stable_user(
    browser: Browser,
    browser_context_args: dict[str, Any],
    api_session: http_requests.Session,
) -> tuple[StableUser, Any]:
    """Shared construction for stable_user / module_stable_user (RULE-04).

    Creates a browser context, registers a fresh user through the REAL
    /register form, and pins the deterministic logged-in state. Returns
    ``(user, context)`` — the caller owns scope and context teardown.

    ONE fresh-user retry on ``PlaywrightTimeoutError`` (absorb-once, commit-
    168945f4 contract): the Oct-14/15 nightlies (runs 38531844492 /
    38700481557) errored fixture setups with ``Page.goto: Timeout 30000ms``
    while the stack was under first-exposure load. A retry registers a NEW
    user in a FRESH context (the aborted attempt's state is discarded).
    ``AssertionError`` is NEVER retried — ``wait_logged_in`` converts a
    /login bounce into AssertionError (E01/N06 regression class), and that
    must stay loud (regression-first, no auto-healing).
    """
    from tests.e2e.helpers.audit_user import build_stable_session

    context = browser.new_context(**browser_context_args)
    page = context.new_page()
    page.add_init_script("localStorage.setItem('narrare:featureTourCompleted', 'true');")
    try:
        session = build_stable_session(page, BASE_URL, api_session, API_URL)
    except PlaywrightTimeoutError:
        time.sleep(_TRANSIENT_BACKOFF_S)
        context.close()
        context = browser.new_context(**browser_context_args)
        page = context.new_page()
        page.add_init_script("localStorage.setItem('narrare:featureTourCompleted', 'true');")
        session = build_stable_session(page, BASE_URL, api_session, API_URL)
    user = StableUser(
        page=page,
        email=session["email"],
        password=session["password"],
        access_token=session["access_token"],
    )
    return user, context


@pytest.fixture
def stable_user(
    browser: Browser,
    browser_context_args: dict[str, Any],
    api_session: http_requests.Session,
) -> Generator[StableUser]:
    """Fresh UI-registered user + stable session (spec §4; N06 mitigation).

    PO ruling (2026-10-13): ALL registration goes through the REAL
    /register form — fill form → POST /auth/register → auto-login (the
    audit-proven flow) — driven by audit_user.build_stable_session. No
    API-registration shortcut. Function scope is the isolation default:
    one UI registration + one browser context per test. Prefer
    module_stable_user when the module doesn't need that isolation.
    """
    user, context = _new_stable_user(browser, browser_context_args, api_session)
    yield user
    context.close()


@pytest.fixture(scope="module")
def module_stable_user(
    browser: Browser,
    browser_context_args: dict[str, Any],
    api_session: http_requests.Session,
) -> Generator[StableUser]:
    """Module-scoped stable_user: ONE UI registration per spec module.

    Fixture-scoping guidance (PO 2026-10-13, suite budget ≤ 25 min): UI
    registration costs a few seconds; sharing one user — and one page —
    across a module keeps per-spec registration cheap. Safe ONLY when no
    test in the module mutates user-level state (settings, credentials,
    feature-tour flags, auth store) or logs out; otherwise use the
    function-scoped stable_user. Tests sharing the page run sequentially
    within the module — navigate explicitly at each test start. Depends
    only on session-scoped fixtures (browser, browser_context_args,
    api_session), so module scope is legal; session scope is possible via
    the same _new_stable_user but discouraged (cross-area state bleed).
    """
    user, context = _new_stable_user(browser, browser_context_args, api_session)
    yield user
    context.close()


@pytest.fixture
def stable_novel(stable_user: StableUser) -> NovelContext:
    """stable_user + blank-starter wizard completion → novel editor."""
    novel = complete_wizard(stable_user.page, BASE_URL)
    return NovelContext(
        page=stable_user.page,
        novel_id=novel["novel_id"],
        email=stable_user.email,
        password=stable_user.password,
        access_token=stable_user.access_token,
    )
