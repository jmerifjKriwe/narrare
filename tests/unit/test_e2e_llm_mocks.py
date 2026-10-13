"""Unit tests for mock_llm() — catalog → page.route installation (no browser).

A fake page records route handlers; a fake route verifies dispatch:
method match + url_exclude respected + fallback otherwise.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from tests.e2e.helpers.llm_mocks import mock_llm
from tests.e2e.mocks.catalog import RouteSpec, entries_for


class _FakeRoute:
    def __init__(self, method: str, url: str) -> None:
        self.request = SimpleNamespace(method=method, url=url)
        self.fulfilled: dict[str, Any] | None = None
        self.fell_back = False

    def fulfill(self, **kwargs: Any) -> None:
        self.fulfilled = kwargs

    def fallback(self) -> None:
        self.fell_back = True


class _FakePage:
    def __init__(self) -> None:
        self.routes: list[tuple[str, Any]] = []

    def route(self, pattern: str, handler: Any) -> None:
        self.routes.append((pattern, handler))


class TestMockLlm:
    def test_installs_one_handler_per_catalog_spec(self) -> None:
        page = _FakePage()
        specs = mock_llm(page, "kb_improve", fixture="happy")

        assert len(page.routes) == len(specs) == 1
        assert page.routes[0][0] == specs[0].pattern

    def test_handler_fulfills_with_spec_body(self) -> None:
        page = _FakePage()
        specs = mock_llm(page, "beta_reader", fixture="happy")
        handler = page.routes[0][1]
        spec = specs[0]

        route = _FakeRoute("POST", "http://localhost:3000/api/v1/analysis/beta-reader?novel_id=x")
        handler(route)

        assert route.fulfilled is not None
        assert route.fulfilled["status"] == spec.status
        assert route.fulfilled["body"] == spec.body
        assert route.fulfilled["content_type"] == spec.content_type

    def test_handler_falls_back_on_method_mismatch(self) -> None:
        page = _FakePage()
        mock_llm(page, "generation_stream", fixture="happy")
        handler = page.routes[0][1]

        route = _FakeRoute("POST", "http://localhost:3000/api/v1/writing/generation/x/stream")
        handler(route)

        assert route.fell_back is True
        assert route.fulfilled is None

    def test_handler_falls_back_on_url_exclude(self) -> None:
        page = _FakePage()
        mock_llm(page, "beta_reader", fixture="happy")
        handler = page.routes[0][1]

        route = _FakeRoute(
            "POST", "http://localhost:3000/api/v1/analysis/beta-reader/deep-dive?novel_id=x"
        )
        handler(route)

        assert route.fell_back is True

    def test_raises_for_unknown_capability(self) -> None:
        with pytest.raises(ValueError, match="Unknown capability/variant"):
            mock_llm(_FakePage(), "telepathy")

    def test_every_happy_spec_body_matches_its_catalog_entry(self) -> None:
        # Cross-check: each installed handler serves exactly its catalog entry.
        page = _FakePage()
        catalog_specs = entries_for("consistency_check", "happy")
        installed: list[RouteSpec] = []
        for spec in catalog_specs:
            installed.extend(mock_llm(page, spec.capability, fixture=spec.variant))

        assert len(page.routes) == len(installed) == len(catalog_specs)
        for (_, handler), spec in zip(page.routes, installed, strict=True):
            route = _FakeRoute(
                spec.method, "http://localhost:3000/api/v1/consistency/check?novel_id=x"
            )
            handler(route)

            assert route.fell_back is False
            assert route.fulfilled is not None
            assert route.fulfilled["status"] == spec.status
            assert route.fulfilled["content_type"] == spec.content_type
            assert route.fulfilled["body"] == spec.body
