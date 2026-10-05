"""Strict pricing resolution — exact-model rates only, cache rates surfaced."""

from __future__ import annotations

import narrare_core.llm.cost_rates as _cr
from narrare_core.llm.model_pricing import _rates_from_metadata, resolve_model_rates


def _meta(cost: dict) -> dict:
    return {"models": {"glm-5.3": {"cost": cost}}}


def test_strict_unknown_model_returns_none_even_for_known_provider():
    # Provider has DEFAULT_RATES entry, model absent from metadata
    result = resolve_model_rates(
        "openai",
        "totally-unknown-model",
        load_cache=lambda: {"models": {}},
        fetch_models=lambda: (_ for _ in ()).throw(AssertionError("must not fetch when cache hit")),
        save_cache=lambda _d: None,
        strict=True,
    )
    assert result is None


def test_non_strict_keeps_fallback_behavior():
    result = resolve_model_rates(
        "openai",
        "totally-unknown-model",
        load_cache=lambda: {"models": {}},
        fetch_models=lambda: {"models": {}},
        save_cache=lambda _d: None,
    )
    assert result == {"input": 10.0, "output": 30.0}


def test_metadata_surfaces_cache_rates():
    rates = _rates_from_metadata(
        "zai",
        "glm-5.3",
        _meta({"input": 1.0, "output": 2.0, "cache_read": 0.1, "cache_write": 2.0}),
    )
    assert rates is not None
    assert rates["input"] == 1.0 and rates["output"] == 2.0
    assert rates["cache_read"] == 0.1 and rates["cache_write"] == 2.0


def test_metadata_without_cache_rates_omits_keys():
    rates = _rates_from_metadata("zai", "glm-5.3", _meta({"input": 1.0, "output": 2.0}))
    assert rates is not None
    assert "cache_read" not in rates and "cache_write" not in rates


def test_strict_fetch_failure_returns_none(monkeypatch):
    def _boom():
        raise RuntimeError("network down")

    result = resolve_model_rates(
        "openai",
        "gpt-4o",
        load_cache=lambda: None,
        fetch_models=_boom,
        save_cache=lambda _d: None,
        strict=True,
    )
    assert result is None


def test_get_rates_strict_with_cached_model_returns_exact_rates(monkeypatch):
    monkeypatch.setattr(
        _cr,
        "_load_cache",
        lambda: {"models": {"glm-5.3": {"cost": {"input": 1.0, "output": 2.0}}}},
    )
    rates = _cr.get_rates_strict("zai", "glm-5.3")
    assert rates == {"input": 1.0, "output": 2.0}


def test_get_rates_strict_with_empty_metadata_returns_none(monkeypatch):
    monkeypatch.setattr(_cr, "_load_cache", lambda: {"models": {}})
    assert _cr.get_rates_strict("openai", "totally-unknown-model") is None
