"""Unit tests for the E2E stable-session helpers.

Concern 2 of ``tests/e2e/helpers/audit_user.py`` (concern 1 — registration
through the UI — lives in ``test_e2e_audit_user.py``). Browser-free via the
shared doubles in ``tests/fakes/fake_e2e_page.py`` /
``fake_e2e_api_session.py``. What is pinned here:

- ``build_stable_session`` establishes deterministic logged-in state BEFORE
  test bodies: register → harvest → attach → wait, in that exact order (the
  N06 mitigation), with login-ONLY token harvest (PO ruling 2026-10-13).
- Stable session ≠ auto-healing: a bounce FAILS loudly with actionable
  E01/N06 guidance; nothing re-logs-in behind the test's back.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.e2e.helpers import (
    attach_session as pkg_attach_session,
)
from tests.e2e.helpers import (
    build_stable_session as pkg_build_stable_session,
)
from tests.e2e.helpers import (
    wait_logged_in as pkg_wait_logged_in,
)
from tests.e2e.helpers.audit_user import (
    attach_session,
    build_stable_session,
    wait_logged_in,
)
from tests.fakes.fake_e2e_api_session import FakeE2EApiSession, FakeE2EResponse
from tests.fakes.fake_e2e_page import FakeE2EPage, FakeE2ERoute

BASE_URL = "http://localhost:3001"
API_URL = "http://localhost:8000"


def _api_session_with_tokens() -> FakeE2EApiSession:
    return FakeE2EApiSession(
        FakeE2EResponse(
            200,
            {"access_token": "at-123", "refresh_token": "rt-456"},
            '{"access_token": "at-123", "refresh_token": "rt-456"}',
        )
    )


class TestPackageReExports:
    def test_helpers_reexported_from_package_match_module(self) -> None:
        assert pkg_attach_session is attach_session
        assert pkg_wait_logged_in is wait_logged_in
        assert pkg_build_stable_session is build_stable_session


class TestAttachSession:
    def test_attach_installs_narrare_auth_cookie_init_script(self) -> None:
        page = FakeE2EPage()

        attach_session(page, "token-abc")

        assert len(page.init_scripts) == 1
        assert "narrare_auth=token-abc" in page.init_scripts[0]
        assert "path=/" in page.init_scripts[0]

    def test_attach_installs_auth_proxy_route_with_bearer_token(self) -> None:
        page = FakeE2EPage()

        attach_session(page, "token-abc")

        assert [pattern for pattern, _ in page.routes] == ["**/api/v1/**"]
        route = FakeE2ERoute()
        handler = page.routes[0][1]

        handler(route)

        assert route.fetch_headers is not None
        assert route.fetch_headers["Authorization"] == "Bearer token-abc"
        assert route.fulfilled is not None
        assert route.fulfilled["status"] == 200


class TestWaitLoggedIn:
    def test_wait_navigates_root_and_pins_not_login_state(self) -> None:
        page = FakeE2EPage()

        wait_logged_in(page, BASE_URL)

        assert page.gotos == [BASE_URL]
        assert page.events[0] == ("goto", BASE_URL, "domcontentloaded")
        assert len(page.wait_for_function_calls) == 1
        expression, timeout = page.wait_for_function_calls[0]
        assert "location.pathname" in expression
        assert "/login" in expression
        assert timeout == "15000"

    def test_wait_bounce_to_login_fails_loud_with_e01_n06_guidance(self) -> None:
        page = FakeE2EPage()
        page.wait_for_function_exc = PlaywrightTimeoutError("still on /login")

        with pytest.raises(AssertionError) as exc_info:
            wait_logged_in(page, BASE_URL)

        message = str(exc_info.value)
        assert "AUTH_JWT_SECRET" in message  # E01 class guidance
        assert "N06" in message  # N06 class guidance
        # The cause chain keeps the original Playwright error (RULE-11).
        assert exc_info.value.__cause__ is page.wait_for_function_exc

    def test_wait_custom_timeout_reaches_wait(self) -> None:
        page = FakeE2EPage()

        wait_logged_in(page, BASE_URL, timeout=1234)

        assert page.wait_for_function_calls[0][1] == "1234"


class TestBuildStableSession:
    def test_build_registers_via_ui_harvests_tokens_and_pins_logged_in_state(
        self,
    ) -> None:
        page, session = FakeE2EPage(), _api_session_with_tokens()

        result = build_stable_session(page, BASE_URL, session, API_URL)

        assert result["password"] == "E2eTest123!pass"
        assert result["display_name"] == "E2E Audit User"
        assert result["access_token"] == "at-123"
        assert result["refresh_token"] == "rt-456"
        assert set(result) == {
            "email",
            "password",
            "display_name",
            "access_token",
            "refresh_token",
        }
        # 1. Registration through the REAL UI form (PO ruling 2026-10-13) —
        #    the first navigation is /register, with the three form fills.
        assert page.events[0] == ("goto", f"{BASE_URL}/register", "")
        assert page.fill_calls == [
            ("#register-display-name", "E2E Audit User"),
            ("#register-email", result["email"]),
            ("#register-password", "E2eTest123!pass"),
        ]
        # 2. Token harvest is login-ONLY: exactly one POST, to the login
        #    endpoint, with the UI-registered identity. No API registration
        #    shortcut may ever exist again.
        assert session.posts == [
            (
                f"{API_URL}/api/v1/auth/login",
                {"email": result["email"], "password": "E2eTest123!pass"},
            )
        ]
        # 3. N06 ordering: the auth cookie init script is attached BEFORE the
        #    final navigation whose logged-in state the wait pins.
        tags = [e[0] for e in page.events]
        assert tags == [
            "goto",  # /register
            "locator_wait",
            "fill",
            "fill",
            "fill",
            "click",
            "wait_for_url",
            "init_script",
            "route",
            "goto",  # base_url (wait_logged_in)
            "wait_for_function",
        ]
        # 4. The logged-in state is explicitly pinned exactly once.
        assert len(page.wait_for_function_calls) == 1
        # 5. Exactly one auth-proxy route install.
        assert [pattern for pattern, _ in page.routes] == ["**/api/v1/**"]

    def test_build_generates_unique_email_per_call(self) -> None:
        sessions = [_api_session_with_tokens() for _ in range(2)]

        result_one = build_stable_session(FakeE2EPage(), BASE_URL, sessions[0], API_URL)
        result_two = build_stable_session(FakeE2EPage(), BASE_URL, sessions[1], API_URL)

        assert result_one["email"] != result_two["email"]
        assert sessions[0].posts[0][1]["email"] == result_one["email"]
        assert sessions[1].posts[0][1]["email"] == result_two["email"]

    def test_build_bounce_after_attach_fails_loud_without_auto_heal(self) -> None:
        page, session = FakeE2EPage(), _api_session_with_tokens()
        page.wait_for_function_exc = PlaywrightTimeoutError("bounced to /login")

        with pytest.raises(AssertionError, match="AUTH_JWT_SECRET"):
            build_stable_session(page, BASE_URL, session, API_URL)

        # No silent re-login behind the test's back: exactly one harvest POST.
        assert len(session.posts) == 1
