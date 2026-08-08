"""Regression guard: unit tests never perform real models.dev network I/O.

Pin for the test-isolation bug fixed alongside the ``_block_models_dev_network``
autouse fixture in ``tests/unit/conftest.py``. Before that guard, several unit
tests reached ``narrare_core.llm.cost_rates._fetch_models`` transitively (via
``ModelRegistry.run()`` → ``cost_estimate_usd`` → ``get_rates``, and the
WebSocket draft path → ``run_limits.resolve`` → ``get_model_limits``) without
mocking it. ``_fetch_models`` performs a *real synchronous* HTTP GET to
``https://models.dev`` whenever the on-disk cache is missing/stale; blocking the
event loop it intermittently exceeded the 10 s per-test pytest-timeout under
full-suite load → flaky ``Timeout`` failures (seen in ``test_gateway`` and
``test_ws_draft_regression``).

These tests pin the intended unit-test stance: the models.dev path is treated
as *offline*. With a forced cache-miss the fetch boundary is reached, the guard
blocks the real call, and graceful degradation returns deterministic defaults —
no exception, no network, fast.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

import narrare_core.llm.cost_rates as _cr
from narrare_core.llm.cost_rates import _DEFAULT_RATES, get_model_limits, get_rates

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def _force_cache_miss(  # pyright: ignore[reportUnusedFunction] — autouse-style fixture, referenced by name as a test argument, not a direct call. Pyright false-positive.
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Point the cost-rates cache at an empty temp dir (no cache file).

    ``get_rates`` / ``get_model_limits`` therefore cannot satisfy the lookup
    from cache and must reach the fetch boundary — where the unit-test guard
    blocks the real network call. Uses ``monkeypatch`` so the module attribute
    is restored after the test (unlike the leaking ``isolate_cache`` fixture in
    ``test_cost_rates.py``).
    """
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(_cr, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(_cr, "CACHE_FILE", cache_dir / "models_cache.json")


class TestModelsDevNetworkIsolationGuard:
    """The models.dev fetch boundary is blocked in unit tests (RULE-20)."""

    def test_get_rates_returns_defaults_without_network(self, _force_cache_miss: None) -> None:
        """Cache-miss + no explicit mock → offline defaults, deterministically.

        If the ``_block_models_dev_network`` guard is removed this test reaches a
        real network call and becomes flaky/slow — surfacing the regression.
        """
        rates = get_rates("openai", "gpt-4o")
        assert rates is not None
        assert rates["input"] == _DEFAULT_RATES["openai"]["input"]
        assert rates["output"] == _DEFAULT_RATES["openai"]["output"]

    def test_get_model_limits_returns_none_without_network(self, _force_cache_miss: None) -> None:
        """Cache-miss + no explicit mock → None (offline graceful degradation)."""
        assert get_model_limits("openai", "gpt-4o") is None

    def test_fetch_boundary_is_blocked_not_real(self) -> None:
        """The guard replaces ``_fetch_models`` with a blocking sentinel.

        A direct pin that the unit-test environment does not expose the real
        network-bound ``_fetch_models``. Catches guard removal even in a
        no-network CI where graceful degradation would otherwise mask it.
        """
        # The real ``_fetch_models`` calls ``models_dev_source.fetch_models``;
        # the guard swaps in a test-only blocker with no ``__module__`` of
        # ``narrare_core.llm.cost_rates`` / no closure over ``fetch_models``.
        # Direct attribute access (not an import binding) so we read the *live*,
        # possibly-monkeypatched module attribute.
        sentinel = _cr._fetch_models  # pyright: ignore[reportPrivateUsage]
        assert sentinel.__name__ != "_fetch_models", (
            "unit-test guard is inactive: _fetch_models is the real network-bound "
            "function. tests/unit/conftest.py::_block_models_dev_network must run "
            "(autouse) to block real models.dev HTTP fetches."
        )
