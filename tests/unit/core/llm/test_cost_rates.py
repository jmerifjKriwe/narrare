"""Tests for llm/cost_rates.py — models.dev caching and pricing lookup."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest

import narrare_core.llm.cost_rates as _cr
from narrare_core.llm.cost_rates import (
    _DEFAULT_RATES,
    ModelLimits,
    _ensure_cache_dir,
    _load_cache,
    _save_cache,
    get_cached_data,
    get_model_limits,
    get_rates,
    invalidate_cache,
    refresh_models,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolate_cache(tmp_path: Path) -> None:
    """Redirect CACHE to a temp directory for each test."""
    _cr.CACHE_DIR = tmp_path / ".narrare" / "cache"
    _cr.CACHE_FILE = _cr.CACHE_DIR / "models_cache.json"


@pytest.fixture
def sample_models_data() -> dict[str, object]:
    """A minimal models.dev-like response."""
    return {
        "models": {
            "gpt-4o": {
                "cost": {"input": 2.5, "output": 10.0},
            },
            "claude-sonnet-4-5-20251020": {
                "cost": {"input": 3.0, "output": 15.0},
            },
            "mixtral-8x7b-32768": {
                "cost": {"input": 0.3, "output": 0.6},
            },
        }
    }


@pytest.fixture
def sample_models_with_limits() -> dict[str, object]:
    """models.dev-like response with limit data."""
    return {
        "models": {
            "gpt-4o": {
                "cost": {"input": 2.5, "output": 10.0},
                "limit": {
                    "context": 128000,
                    "output": 16384,
                },
            },
            "claude-sonnet-4-5-20251020": {
                "cost": {"input": 3.0, "output": 15.0},
                "limit": {
                    "context": 200000,
                    "output": 8192,
                },
            },
        }
    }


# ---------------------------------------------------------------------------
# _ensure_cache_dir
# ---------------------------------------------------------------------------


class TestEnsureCacheDir:
    def test_creates_directory(self) -> None:
        assert not _cr.CACHE_DIR.exists()
        result = _ensure_cache_dir()
        assert _cr.CACHE_DIR.exists()
        assert result == _cr.CACHE_DIR

    def test_idempotent_when_exists(self) -> None:
        _ensure_cache_dir()
        result = _ensure_cache_dir()
        assert result == _cr.CACHE_DIR


# ---------------------------------------------------------------------------
# _save_cache / _load_cache
# ---------------------------------------------------------------------------


class TestSaveAndLoadCache:
    def test_save_and_load_roundtrip(self, sample_models_data: dict[str, object]) -> None:
        _ensure_cache_dir()
        _save_cache(sample_models_data)
        assert _cr.CACHE_FILE.exists()

        loaded = _load_cache()
        assert loaded is not None
        assert loaded["models"]["gpt-4o"]["cost"]["input"] == 2.5

    def test_load_returns_none_when_no_cache(self) -> None:
        assert _load_cache() is None

    def test_load_returns_none_when_file_missing(self) -> None:
        """Cache file doesn't exist -> returns None."""
        assert _cr.CACHE_FILE.exists() is False
        assert _load_cache() is None

    def test_load_corrupted_cache_returns_none(self) -> None:
        _ensure_cache_dir()
        _cr.CACHE_FILE.write_text("not valid json", encoding="utf-8")
        assert _load_cache() is None

    def test_load_handles_os_error(self) -> None:
        """When cache file can't be read, returns None."""
        assert _load_cache() is None


# ---------------------------------------------------------------------------
# invalidate_cache
# ---------------------------------------------------------------------------


class TestInvalidateCache:
    def test_invalidate_existing(self, sample_models_data: dict[str, object]) -> None:
        _save_cache(sample_models_data)
        assert _cr.CACHE_FILE.exists()

        result = invalidate_cache()
        assert result is True
        assert not _cr.CACHE_FILE.exists()

    def test_invalidate_nonexistent(self) -> None:
        result = invalidate_cache()
        assert result is False


# ---------------------------------------------------------------------------
# get_rates
# ---------------------------------------------------------------------------


class TestGetRates:
    def test_returns_model_specific_rates(self, sample_models_data: dict[str, object]) -> None:
        """When models.dev data has the model, return its rates."""
        _save_cache(sample_models_data)
        rates = get_rates("openai", "gpt-4o")
        assert rates is not None
        assert rates["input"] == 2.5
        assert rates["output"] == 10.0

    def test_falls_back_to_provider_defaults(self) -> None:
        """When model not in cache, use _DEFAULT_RATES[provider]."""
        with patch(
            "narrare_core.llm.cost_rates._fetch_models",
            side_effect=Exception("Network error"),
        ):
            rates = get_rates("anthropic", "unknown-model")
        assert rates is not None
        assert rates["input"] == _DEFAULT_RATES["anthropic"]["input"]
        assert rates["output"] == _DEFAULT_RATES["anthropic"]["output"]

    def test_returns_none_for_unknown_provider(self) -> None:
        """No model in cache and no default rates for provider -> None."""
        with patch(
            "narrare_core.llm.cost_rates._fetch_models",
            side_effect=Exception("Network error"),
        ):
            rates = get_rates("nonexistent-provider", "some-model")
        assert rates is None

    def test_fetches_and_caches_when_cache_missing(
        self, sample_models_data: dict[str, object]
    ) -> None:
        """When no cache exists, fetch models.dev and cache it."""
        with patch(
            "narrare_core.llm.cost_rates._fetch_models",
            return_value=sample_models_data,
        ):
            rates = get_rates("openai", "gpt-4o")

        assert rates is not None
        assert rates["input"] == 2.5
        assert rates["output"] == 10.0
        assert _cr.CACHE_FILE.exists()

    def test_cached_data_avoids_refetch(self, sample_models_data: dict[str, object]) -> None:
        """When cache is valid, don't fetch again."""
        _save_cache(sample_models_data)

        with patch(
            "narrare_core.llm.cost_rates._fetch_models",
        ) as mock_fetch:
            rates = get_rates("openai", "gpt-4o")

        assert rates is not None
        assert rates["input"] == 2.5
        mock_fetch.assert_not_called()


# ---------------------------------------------------------------------------
# get_cached_data
# ---------------------------------------------------------------------------


class TestGetCachedData:
    def test_returns_none_when_no_cache(self) -> None:
        assert get_cached_data() is None

    def test_returns_cached_data(self, sample_models_data: dict[str, object]) -> None:
        _save_cache(sample_models_data)
        data = get_cached_data()
        assert data is not None
        assert "models" in data


# ---------------------------------------------------------------------------
# refresh_models
# ---------------------------------------------------------------------------


class TestRefreshModels:
    def test_fetches_and_saves(self, sample_models_data: dict[str, object]) -> None:
        with patch(
            "narrare_core.llm.cost_rates._fetch_models",
            return_value=sample_models_data,
        ):
            result = refresh_models()

        assert result == sample_models_data
        assert _cr.CACHE_FILE.exists()

    def test_returns_empty_dict_on_failure(self) -> None:
        with patch(
            "narrare_core.llm.cost_rates._fetch_models",
            side_effect=Exception("Network error"),
        ):
            result = refresh_models()

        assert result == {}

    def test_logs_warning_and_never_raises(self) -> None:
        """refresh_models never raises — graceful degradation."""
        with patch(
            "narrare_core.llm.cost_rates._fetch_models",
            side_effect=Exception("Network error"),
        ):
            result = refresh_models()
            assert result == {}


# ---------------------------------------------------------------------------
# get_model_limits / ModelLimits
# ---------------------------------------------------------------------------


class TestGetModelLimits:
    def test_returns_none_for_unknown_model(self) -> None:
        """Unknown model returns None (graceful degradation)."""
        result = get_model_limits("openai", "nonexistent-model-v42")
        assert result is None

    def test_model_limits_dataclass(self) -> None:
        """ModelLimits dataclass stores context and output."""
        limits = ModelLimits(context=128000, output=16384)
        assert limits.context == 128000
        assert limits.output == 16384

    def test_model_limits_is_frozen(self) -> None:
        """ModelLimits is immutable (frozen dataclass)."""
        limits = ModelLimits(context=128000, output=16384)
        with pytest.raises(AttributeError):
            limits.context = 64000  # type: ignore[misc]

    def test_returns_limits_from_cache(self, sample_models_with_limits: dict[str, object]) -> None:
        """When cache has model with limits, return ModelLimits."""
        _save_cache(sample_models_with_limits)
        result = get_model_limits("openai", "gpt-4o")
        assert result is not None
        assert result.context == 128000
        assert result.output == 16384

    def test_returns_none_when_no_limits_in_data(
        self, sample_models_data: dict[str, object]
    ) -> None:
        """When model has no 'limit' key, return None."""
        _save_cache(sample_models_data)
        result = get_model_limits("openai", "gpt-4o")
        assert result is None

    def test_fetches_and_caches_when_cache_missing(
        self, sample_models_with_limits: dict[str, object]
    ) -> None:
        """When no cache exists, fetch then look up limits."""
        with patch(
            "narrare_core.llm.cost_rates._fetch_models",
            return_value=sample_models_with_limits,
        ):
            result = get_model_limits("openai", "gpt-4o")

        assert result is not None
        assert result.context == 128000
        assert result.output == 16384

    def test_fetch_failure_returns_none(self) -> None:
        """When models.dev is unreachable, return None (graceful degradation)."""
        with patch(
            "narrare_core.llm.cost_rates._fetch_models",
            side_effect=Exception("Network error"),
        ):
            result = get_model_limits("openai", "gpt-4o")

        assert result is None
