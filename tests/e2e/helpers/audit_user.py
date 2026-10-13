"""Auth session helpers: register-through-UI + stable logged-in sessions.

Spec §4 (audit_user). Two concerns:
- ``register_user_via_ui`` — the REAL first-run path and the ONLY
  registration path in the suite (PO ruling 2026-10-13: fill form →
  POST /auth/register → auto-login — the audit-proven flow).
- ``build_stable_session`` — deterministic logged-in state BEFORE test
  bodies: UI registration (auto-login) → one API login to harvest the
  access token → narrare_auth cookie → auth-proxy route → explicit
  logged-in wait. Mitigates the N06/nightly class (memory-only access
  token; reload 401s until refresh; mid-test bounce to /login) by
  removing the race, not by hiding it: a bounce still FAILS the spec
  (regression-first — no auto-healing).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Literal, Protocol, cast

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.e2e.test_helpers import _setup_auth_proxy

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests as http_requests
    from playwright.sync_api import Page, Route

_WaitUntil = Literal["commit", "domcontentloaded", "load", "networkidle"]
_WaitForState = Literal["attached", "detached", "hidden", "visible"]

_FORM_VISIBLE_TIMEOUT_MS: int = 10_000
"""Wait for the /register form to render (SPA route first paint)."""

_AUTO_LOGIN_REDIRECT_TIMEOUT_MS: int = 15_000
"""Auto-login redirect off /register — the audit-proven flow budget (N06)."""


class _VisibleWaitable(Protocol):
    """What the registration-form wait needs from a locator — nothing more."""

    def wait_for(self, *, state: _WaitForState, timeout: float) -> None: ...


class _RegistrationPage(Protocol):
    """What ``register_user_via_ui`` needs from a page — nothing more.

    Structural contract (RULE-03), mirroring ``RoutablePage`` in
    ``llm_mocks.py``: real ``playwright.sync_api.Page`` objects satisfy it,
    and so do the browser-free fakes in the unit tests — with zero
    suppressions (RULE-23: structural typing instead of baseline-grown
    suppression lists).
    """

    def goto(self, url: str, *, wait_until: _WaitUntil | None = None) -> object: ...

    def locator(self, selector: str) -> _VisibleWaitable: ...

    def fill(self, selector: str, value: str) -> None: ...

    def click(self, selector: str) -> None: ...

    def wait_for_url(self, url: Callable[[str], bool], *, timeout: float) -> None: ...


class _NavigationPage(Protocol):
    """What ``wait_logged_in`` needs from a page — nothing more."""

    def goto(self, url: str, *, wait_until: _WaitUntil | None = None) -> object: ...

    def wait_for_function(self, expression: str, *, timeout: float) -> object: ...


class _AuthAttachablePage(Protocol):
    """What session attachment needs from a page — exactly the surface the
    ``_setup_auth_proxy`` delegate touches (cookie init script + proxy route)."""

    def add_init_script(self, script: str) -> object: ...

    def route(self, pattern: str, handler: Callable[[Route], None], /) -> object: ...


class _StableSessionPage(
    _RegistrationPage,
    _NavigationPage,
    _AuthAttachablePage,
):
    """Everything ``build_stable_session`` needs from a page — the composition
    of its three callee contracts; real pages satisfy all three."""


def register_user_via_ui(
    page: _RegistrationPage,
    base_url: str,
    *,
    email: str | None = None,
    password: str | None = None,
    display_name: str = "E2E Audit User",
) -> dict[str, str]:
    """Register through the real /register form and wait for auto-login.

    Returns ``{"email", "password", "display_name"}``. The app auto-logs-in
    after registration (verified working in the 2026-10-11 audit).
    """
    email = email or f"e2e-ui-{uuid.uuid4().hex[:8]}@example.com"
    password = password or "E2eTest123!pass"

    page.goto(f"{base_url}/register")
    page.locator("#register-display-name").wait_for(
        state="visible", timeout=_FORM_VISIBLE_TIMEOUT_MS
    )
    page.fill("#register-display-name", display_name)
    page.fill("#register-email", email)
    page.fill("#register-password", password)
    page.click('button[type="submit"]')

    # Auto-login redirect: land anywhere that is NOT /register or /login.
    page.wait_for_url(
        lambda url: "/register" not in url and "/login" not in url,
        timeout=_AUTO_LOGIN_REDIRECT_TIMEOUT_MS,
    )
    return {"email": email, "password": password, "display_name": display_name}


def login_via_api(
    api_session: http_requests.Session,
    api_url: str,
    email: str,
    password: str,
) -> dict[str, str]:
    """Login via the API (browser-mimic Origin) → ``{access_token, refresh_token}``.

    Login ONLY: harvests tokens for an existing (UI-registered) user so the
    browser session can carry the narrare_auth cookie + proxy route. Never
    registers — ALL registration goes through the UI (PO ruling 2026-10-13).
    """
    resp = api_session.post(
        f"{api_url}/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, (
        f"API login failed for {email}: {resp.status_code} {resp.text[:300]}"
    )
    data = resp.json()
    return {"access_token": data["access_token"], "refresh_token": data["refresh_token"]}


def attach_session(page: _AuthAttachablePage, access_token: str) -> None:
    """Attach an API-issued token to the page (cookie + auth-proxy route).

    Delegates to ``_setup_auth_proxy`` — no duplication. The ``cast`` is the
    boundary adapter: the delegate is typed against the full playwright
    ``Page`` (tests/e2e/test_helpers.py — outside this module's scope to
    retype), but it only touches the two members ``_AuthAttachablePage``
    guarantees (``add_init_script`` + ``route``), so the narrow contract is
    sufficient and the adapter is a no-op at runtime.
    """
    _setup_auth_proxy(cast("Page", page), access_token)


def wait_logged_in(page: _NavigationPage, base_url: str, timeout: int = 15_000) -> None:
    """Navigate to the app root and FAIL loudly if bounced to /login."""
    page.goto(base_url, wait_until="domcontentloaded")
    try:
        page.wait_for_function(
            "() => !window.location.pathname.startsWith('/login')",
            timeout=timeout,
        )
    except PlaywrightTimeoutError as exc:
        raise AssertionError(
            "Navigation bounced to /login — the app/proxy rejected the session. "
            "E01 class: is AUTH_JWT_SECRET exported to the web process and equal "
            "to the API's signing key? N06 class: did the access token never "
            "hydrate (check attach_session order vs first goto)?"
        ) from exc


def build_stable_session(
    page: _StableSessionPage,
    base_url: str,
    api_session: http_requests.Session,
    api_url: str,
    *,
    email: str | None = None,
    password: str = "E2eTest123!pass",
    display_name: str = "E2E Audit User",
) -> dict[str, str]:
    """UI registration + deterministic logged-in state; returns creds + tokens.

    Registration goes through the REAL /register form (PO ruling
    2026-10-13) via :func:`register_user_via_ui` — fill form →
    POST /auth/register → auto-login. The auto-login session is then made
    deterministic: one API login harvests a fresh access token for the
    narrare_auth cookie + auth-proxy route (the UI keeps its token in
    memory only — N06), and ``wait_logged_in`` pins the state.

    ``email=None`` generates one unique address per call, so the calling
    fixture's scope fixes the user identity — call once per module for a
    shared registration, once per test for full isolation.
    """
    user = register_user_via_ui(
        page, base_url, email=email, password=password, display_name=display_name
    )
    tokens = login_via_api(api_session, api_url, user["email"], user["password"])
    attach_session(page, tokens["access_token"])
    wait_logged_in(page, base_url)
    return {**user, **tokens}
