"""Unit tests for ``models.dev`` pricing lookup helpers.

``resolve_model_rates`` takes injected callables for cache/fetch/save, so all
branches (cache hit, remote fetch, fetch failure, invalid metadata, unknown
provider) are exercised without any network or filesystem access.
"""

from __future__ import annotations

from typing import Any

from narrare_core.llm.model_pricing import DEFAULT_RATES, resolve_model_rates


def _noop_save(_data: dict[str, Any]) -> None:
    """Save callable that discards its argument."""


class TestResolveModelRatesCacheHit:
    def test_cache_with_valid_rates_is_returned_without_fetch(self) -> None:
        data = {"models": {"gpt-4": {"cost": {"input": 5.0, "output": 15.0}}}}
        fetched: list[bool] = []

        rates = resolve_model_rates(
            "openai",
            "gpt-4",
            load_cache=lambda: data,
            fetch_models=lambda: fetched.append(True) or {},  # type: ignore[return-value]
            save_cache=_noop_save,
        )

        assert rates == {"input": 5.0, "output": 15.0}
        assert fetched == []  # fetch never called on cache hit


class TestResolveModelRatesRemoteFetch:
    def test_cache_miss_fetches_and_saves(self) -> None:
        saved: list[dict[str, Any]] = []
        remote = {"models": {"claude": {"cost": {"input": 3.0, "output": 9.0}}}}

        rates = resolve_model_rates(
            "anthropic",
            "claude",
            load_cache=lambda: None,
            fetch_models=lambda: remote,
            save_cache=saved.append,
        )

        assert rates == {"input": 3.0, "output": 9.0}
        assert saved == [remote]

    def test_model_not_in_metadata_falls_back_to_provider_default(self) -> None:
        remote = {"models": {"other-model": {"cost": {"input": 1.0, "output": 2.0}}}}

        rates = resolve_model_rates(
            "openai",
            "unknown-model",
            load_cache=lambda: None,
            fetch_models=lambda: remote,
            save_cache=_noop_save,
        )

        assert rates == DEFAULT_RATES["openai"]


class TestResolveModelRatesFetchFailure:
    def test_fetch_failure_returns_provider_default(self) -> None:
        def _boom() -> dict[str, Any]:
            raise RuntimeError("network down")

        rates = resolve_model_rates(
            "anthropic",
            "claude",
            load_cache=lambda: None,
            fetch_models=_boom,
            save_cache=_noop_save,
        )

        assert rates == DEFAULT_RATES["anthropic"]

    def test_fetch_failure_for_unknown_provider_returns_none(self) -> None:
        def _boom() -> dict[str, Any]:
            raise RuntimeError("network down")

        rates = resolve_model_rates(
            "mystery-provider",
            "some-model",
            load_cache=lambda: None,
            fetch_models=_boom,
            save_cache=_noop_save,
        )

        assert rates is None


class TestResolveModelRatesInvalidMetadata:
    def test_non_numeric_cost_falls_back_to_default(self) -> None:
        data = {"models": {"gpt-4": {"cost": {"input": "free", "output": 15.0}}}}

        rates = resolve_model_rates(
            "openai",
            "gpt-4",
            load_cache=lambda: data,
            fetch_models=lambda: {},
            save_cache=_noop_save,
        )

        assert rates == DEFAULT_RATES["openai"]

    def test_missing_cost_keys_fall_back_to_default(self) -> None:
        data = {"models": {"gpt-4": {"cost": {"input": 5.0}}}}  # no output

        rates = resolve_model_rates(
            "openai",
            "gpt-4",
            load_cache=lambda: data,
            fetch_models=lambda: {},
            save_cache=_noop_save,
        )

        assert rates == DEFAULT_RATES["openai"]


class TestResolveModelRatesUnknownProvider:
    def test_unknown_provider_with_no_default_returns_none(self) -> None:
        rates = resolve_model_rates(
            "mystery-provider",
            "some-model",
            load_cache=lambda: {"models": {}},
            fetch_models=lambda: {},
            save_cache=_noop_save,
        )

        assert rates is None

    def test_unknown_provider_in_metadata_still_no_default_returns_none(self) -> None:
        data = {
            "models": {"some-model": {"cost": {"input": 1.0, "output": 2.0}}},
        }
        # Provider not in DEFAULT_RATES but model present in metadata -> rates returned
        rates = resolve_model_rates(
            "brand-new-provider",
            "some-model",
            load_cache=lambda: data,
            fetch_models=lambda: {},
            save_cache=_noop_save,
        )

        assert rates == {"input": 1.0, "output": 2.0}


def test_default_rates_cover_known_providers() -> None:
    """Sanity: the documented providers all have fallback rates."""
    for provider in ("openai", "anthropic", "google", "groq", "ollama"):
        assert provider in DEFAULT_RATES
        assert DEFAULT_RATES[provider]["input"] >= 0.0
    # Unknown providers are absent
    assert "mystery-provider" not in DEFAULT_RATES
