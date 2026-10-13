"""Environment smoke pins (spec §8) + foundation fixture self-check.

Fails FAST and ACTIONABLY on the environment couplings the 2026-10-11
audit found (E01/E04) so per-area specs never debug infrastructure:
- E01: proxy must keep an authenticated user OUT of /login.
- Spec §3: zero browser-side LLM provider calls.
- Spec §10: mock_llm serves exactly what the catalog validated.
- Foundation: stable_user/stable_novel fixtures reach the editor.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from tests.e2e.helpers import capture_console, capture_network, dump_a11y, mock_llm

if TYPE_CHECKING:
    from playwright.sync_api import Page

_E01_MSG = (
    "Bounced to /login while authenticated — E01: the Next.js proxy verifies "
    "narrare_auth with AUTH_JWT_SECRET ?? SECRET_KEY ?? dev-default. Is "
    "AUTH_JWT_SECRET exported to the web process and equal to the API's "
    "signing key? (scripts/run_e2e.sh exports it; standalone `pnpm dev` "
    "starts do NOT inherit it.)"
)


@pytest.mark.e2e
class TestEnvironmentSmoke:
    def test_proxy_keeps_authenticated_user_out_of_login(
        self, authenticated_page: Page, base_url: str
    ) -> None:
        """E01 pin — protected navigation must not bounce to /login."""
        authenticated_page.goto(f"{base_url}/dashboard")
        authenticated_page.wait_for_load_state("domcontentloaded")
        assert "/login" not in authenticated_page.url, _E01_MSG

    def test_browser_never_calls_llm_providers(self, fresh_page: Page, base_url: str) -> None:
        """Spec §3 pin — no browser-side request to any provider host."""
        network = capture_network(fresh_page)
        console = capture_console(fresh_page)
        fresh_page.goto(base_url)
        fresh_page.goto(f"{base_url}/login")
        network.assert_no_provider_calls()
        console.assert_no_page_errors()

    def test_mock_llm_fulfills_catalog_entry_via_page_route(
        self, fresh_page: Page, base_url: str
    ) -> None:
        """mock_llm + catalog end-to-end: an in-page fetch gets the fixture."""
        from tests.e2e.mocks.catalog import entries_for

        mock_llm(fresh_page, "beta_reader")
        expected = json.loads(entries_for("beta_reader", "happy")[0].body)

        fresh_page.goto(base_url)
        result = fresh_page.evaluate(
            """async () => {
                const resp = await fetch(
                    '/api/v1/analysis/beta-reader?novel_id=00000000-0000-0000-0000-0000000000f1',
                    {method: 'POST'},
                );
                return {status: resp.status, body: await resp.json()};
            }"""
        )
        assert result["status"] == 200
        assert result["body"] == expected

    def test_a11y_dump_captures_tree(self, fresh_page: Page, base_url: str) -> None:
        """probes.dump_a11y produces a parseable AXTree for debugging."""
        from pathlib import Path

        fresh_page.goto(f"{base_url}/login")
        out = dump_a11y(fresh_page, Path("test-results") / "a11y-login.json")
        tree = json.loads(out.read_text(encoding="utf-8"))
        # dump_a11y writes the raw CDP Accessibility.getFullAXTree response:
        # {"nodes": [...]} with role as {type, value} (see the unit pin in
        # tests/unit/test_e2e_probes.py::TestDumpA11y). Live Chromium names
        # the root "RootWebArea" (internalRole); the Playwright
        # accessibility-snapshot naming is "WebArea". The tree is intact
        # iff it contains the web-area root node under either name.
        assert any(
            node.get("role", {}).get("value") in ("RootWebArea", "WebArea")
            for node in tree["nodes"]
        ), "AXTree dump must contain the web-area root node"


@pytest.mark.e2e
class TestFoundationFixtures:
    def test_stable_user_reaches_app_root_logged_in(self, stable_user) -> None:
        """stable_user self-check: deterministic session, not on /login."""
        assert "/login" not in stable_user.page.url

    def test_stable_novel_reaches_editor(self, stable_novel) -> None:
        """stable_novel self-check: fresh user + wizard → novel editor URL."""
        assert "/novel/" in stable_novel.page.url
        assert stable_novel.novel_id

    def test_module_stable_user_shares_one_ui_registration(self, module_stable_user) -> None:
        """module_stable_user self-check: module-scoped UI-registered session."""
        assert "/login" not in module_stable_user.page.url
        assert module_stable_user.email.startswith("e2e-ui-")


@pytest.mark.e2e
class TestCatalogValidationFailure:
    def test_validate_catalog_wraps_module_validator_failure_with_context(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Failure branch (T3/T5 review carry-forward): a broken module
        validator must raise RuntimeError NAMING the failing catalog module
        (RULE-11: loud, contextual failures — never silent)."""
        from tests.e2e.mocks import catalog as catalog_module

        def _broken_validate() -> None:
            raise ValueError("malformed spec: body is not valid JSON")

        monkeypatch.setattr("tests.e2e.mocks.catalog_writing.validate", _broken_validate)
        with pytest.raises(RuntimeError, match="catalog_writing"):
            catalog_module.validate_catalog()
