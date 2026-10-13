"""Consolidated helper package for the E2E suite (spec §4).

One responsibility per module (RULE-04):
- probes       — console/network observation + a11y dumps
- llm_mocks    — mock_llm() installs catalog fixtures via page.route()
- audit_user   — registration-through-UI + stable logged-in sessions
- novel_factory— wizard completion + volume/chapter API setup
"""

from tests.e2e.helpers.audit_user import (
    attach_session,
    build_stable_session,
    login_via_api,
    register_user_via_ui,
    wait_logged_in,
)
from tests.e2e.helpers.llm_mocks import mock_llm
from tests.e2e.helpers.probes import (
    PROVIDER_HOSTS,
    ConsoleCapture,
    NetworkCapture,
    capture_console,
    capture_network,
    dump_a11y,
)

__all__ = [
    "PROVIDER_HOSTS",
    "ConsoleCapture",
    "NetworkCapture",
    "attach_session",
    "build_stable_session",
    "capture_console",
    "capture_network",
    "dump_a11y",
    "login_via_api",
    "mock_llm",
    "register_user_via_ui",
    "wait_logged_in",
]
