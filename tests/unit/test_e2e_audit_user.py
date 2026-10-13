"""Unit tests for the E2E registration/login helpers.

Concern 1 of ``tests/e2e/helpers/audit_user.py`` (concern 2 — deterministic
sessions — lives in ``test_e2e_audit_session.py``). Browser-free, mirroring
the fake-page pattern of test_e2e_llm_mocks.py / test_e2e_probes.py via the
shared doubles in ``tests/fakes/fake_e2e_page.py`` /
``fake_e2e_api_session.py``. What is pinned here:

- Registration goes through the UI form only (PO ruling 2026-10-13) and
  generates one unique email per call (the fixture's scope fixes identity).
- ``login_via_api`` is login-ONLY (token harvest for an existing user).
- Every failure propagates loudly (no auto-heal, no retry).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.e2e.helpers import (
    login_via_api as pkg_login_via_api,
)
from tests.e2e.helpers import (
    register_user_via_ui as pkg_register_user_via_ui,
)
from tests.e2e.helpers.audit_user import login_via_api, register_user_via_ui
from tests.fakes.fake_e2e_api_session import FakeE2EApiSession, FakeE2EResponse
from tests.fakes.fake_e2e_page import FakeE2EPage

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
        # Specs consume the helpers via the package (helpers/__init__.py);
        # the re-exports must be the module's own objects, not accidental copies.
        assert pkg_register_user_via_ui is register_user_via_ui
        assert pkg_login_via_api is login_via_api


class TestRegisterUserViaUi:
    def test_register_with_explicit_credentials_fills_form_and_returns_identity(
        self,
    ) -> None:
        page = FakeE2EPage()

        result = register_user_via_ui(
            page,
            BASE_URL,
            email="auditor@example.com",
            password="Sup3rSecret!",
            display_name="Audit Person",
        )

        assert result == {
            "email": "auditor@example.com",
            "password": "Sup3rSecret!",
            "display_name": "Audit Person",
        }
        assert page.gotos == [f"{BASE_URL}/register"]
        assert page.fill_calls == [
            ("#register-display-name", "Audit Person"),
            ("#register-email", "auditor@example.com"),
            ("#register-password", "Sup3rSecret!"),
        ]
        assert page.clicks == ['button[type="submit"]']

    def test_register_generates_unique_email_when_none_given(self) -> None:
        page_one, page_two = FakeE2EPage(), FakeE2EPage()

        result_one = register_user_via_ui(page_one, BASE_URL)
        result_two = register_user_via_ui(page_two, BASE_URL)

        assert result_one["email"] != result_two["email"]
        for result in (result_one, result_two):
            local, domain = result["email"].split("@")
            assert domain == "example.com"
            assert local.startswith("e2e-ui-")
            assert len(local.removeprefix("e2e-ui-")) == 8

    def test_register_uses_default_password_when_none_given(self) -> None:
        page = FakeE2EPage()

        result = register_user_via_ui(page, BASE_URL, email="x@example.com")

        assert result["password"] == "E2eTest123!pass"
        assert ("#register-password", "E2eTest123!pass") in page.fill_calls

    def test_register_waits_for_redirect_off_register_and_login(self) -> None:
        page = FakeE2EPage()

        register_user_via_ui(page, BASE_URL, email="x@example.com")

        # Exactly one redirect wait, at 15 s, with a predicate that rejects
        # both auth routes and accepts any app route (the auto-login pin).
        wait_events = [e for e in page.events if e[0] == "wait_for_url"]
        assert wait_events == [("wait_for_url", "15000")]
        predicate = page.url_predicates[0]
        assert predicate(f"{BASE_URL}/register") is False
        assert predicate(f"{BASE_URL}/login") is False
        assert predicate(f"{BASE_URL}/novels") is True

    def test_register_timeout_propagates_without_retry(self) -> None:
        page = FakeE2EPage()
        page.wait_for_url_exc = PlaywrightTimeoutError("redirect never happened")

        with pytest.raises(PlaywrightTimeoutError):
            register_user_via_ui(page, BASE_URL, email="x@example.com")

        # Fail loud, no auto-heal: exactly one form submit, no retry navigation.
        assert page.gotos == [f"{BASE_URL}/register"]
        assert page.clicks == ['button[type="submit"]']


class TestLoginViaApi:
    def test_login_posts_credentials_to_login_endpoint(self) -> None:
        session = _api_session_with_tokens()

        tokens = login_via_api(session, API_URL, "auditor@example.com", "pw")

        assert tokens == {"access_token": "at-123", "refresh_token": "rt-456"}
        assert session.posts == [
            (
                f"{API_URL}/api/v1/auth/login",
                {"email": "auditor@example.com", "password": "pw"},
            )
        ]

    def test_login_failure_raises_with_status_and_body(self) -> None:
        session = FakeE2EApiSession(FakeE2EResponse(401, {}, '{"detail": "invalid credentials"}'))

        with pytest.raises(AssertionError) as exc_info:
            login_via_api(session, API_URL, "auditor@example.com", "wrong")

        message = str(exc_info.value)
        assert "401" in message
        assert "auditor@example.com" in message
        assert "invalid credentials" in message
