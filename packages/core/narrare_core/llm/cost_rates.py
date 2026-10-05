"""
Model cost data from models.dev with local caching.

Provides per-model pricing lookup for cost estimation.
Cache is stored at ~/.narrare/cache/models_cache.json with 24h TTL.

Graceful degradation: if models.dev is unreachable, stale cache is used,
and if no cache exists, default rates are returned.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import structlog

from narrare_core.llm.model_calibration import (
    ModelLimitCalibration,
    ModelLimitMetadataSnapshot,
    ModelLimits,
    calibrate_model_limits,
)
from narrare_core.llm.model_pricing import DEFAULT_RATES, resolve_model_rates
from narrare_core.llm.models_dev_source import (
    CACHE_TTL,
    FETCH_TIMEOUT,
    ModelMetadataCacheSnapshot,
    fetch_models,
    load_cache_snapshot,
    save_cache,
)

logger = structlog.get_logger(__name__)

MODELS_DEV_URL = "https://models.dev/api.json"
CACHE_DIR = Path.home() / ".narrare" / "cache"
CACHE_FILE = CACHE_DIR / "models_cache.json"
_DEFAULT_RATES = DEFAULT_RATES

__all__ = [
    "CACHE_DIR",
    "CACHE_FILE",
    "MODELS_DEV_URL",
    "_DEFAULT_RATES",
    "ModelLimitCalibration",
    "ModelLimits",
    "get_cached_data",
    "get_model_limit_calibration",
    "get_model_limits",
    "get_rates",
    "get_rates_strict",
    "invalidate_cache",
    "refresh_models",
]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_cache_dir() -> Path:
    """Create the cache directory if it does not exist.

    Returns:
        The cache directory path.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def _load_cache_snapshot(cache_ttl: int = CACHE_TTL) -> ModelMetadataCacheSnapshot:
    """Load cache data with freshness evidence."""

    return load_cache_snapshot(CACHE_FILE, cache_ttl=cache_ttl)


def _load_cache(cache_ttl: int = CACHE_TTL) -> dict[str, Any] | None:
    """Load the local models.dev cache if it exists and is still fresh.

    Cache is considered valid if the file's mtime is less than
    *cache_ttl* seconds old.

    Returns:
        Parsed JSON data as dict, or None if no valid cache exists.
    """
    snapshot = _load_cache_snapshot(cache_ttl=cache_ttl)
    if snapshot.is_fresh:
        return snapshot.data
    return None


def _fetch_models(*, timeout: float = FETCH_TIMEOUT) -> dict[str, Any]:
    """Fetch the models.dev dataset from the remote API.

    Args:
        timeout: Request timeout in seconds.

    Returns:
        Parsed JSON response as a dict.

    Raises:
        httpx.HTTPError: On connection or HTTP errors.
        json.JSONDecodeError: On invalid JSON response.
    """
    return fetch_models(MODELS_DEV_URL, timeout=timeout)


def _save_cache(data: dict[str, Any]) -> None:
    """Save fetched models.dev data to the local cache file.

    Args:
        data: The models.dev JSON data to cache.
    """
    _ensure_cache_dir()
    save_cache(CACHE_DIR, CACHE_FILE, data)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def invalidate_cache() -> bool:
    """Delete the local models.dev cache file.

    Returns:
        True if the cache was deleted, False if it did not exist.
    """
    try:
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
            logger.info("models_cache_invalidated", file=str(CACHE_FILE))
            return True
        return False
    except OSError as exc:
        logger.warning("models_cache_invalidate_failed", error=str(exc))
        return False


def get_rates(provider: str, model_id: str) -> dict[str, float] | None:
    """Look up per-model pricing from models.dev, with fallback defaults.

    Resolution order:
    1. Load from local cache (or fetch if cache is missing/expired)
    2. Look up ``model_id`` in the cached model data
    3. Fall back to ``_DEFAULT_RATES[provider]``
    4. If nothing found, return ``None``

    Args:
        provider: Provider name (e.g. "openai", "anthropic").
        model_id: Model identifier (e.g. "gpt-4o", "claude-sonnet-4-5-20251020").

    Returns:
        A dict with ``input`` and ``output`` keys (USD per 1M tokens),
        or ``None`` if no rates could be determined.
    """
    return resolve_model_rates(
        provider,
        model_id,
        load_cache=_load_cache,
        fetch_models=_fetch_models,
        save_cache=_save_cache,
    )


def get_rates_strict(provider: str, model_id: str) -> dict[str, float] | None:
    """Look up exact-model pricing from models.dev; never falls back to defaults.

    Returns the metadata rates for exactly ``model_id`` — including
    ``cache_read`` / ``cache_write`` (USD per 1M tokens) when models.dev
    provides them — or ``None`` when the model is unknown or pricing is
    unavailable (unknown model of a known provider ⇒ ``None``).

    Args:
        provider: Provider name (e.g. "openai", "anthropic").
        model_id: Model identifier (e.g. "gpt-4o", "claude-sonnet-4-5-20251020").

    Returns:
        A dict with ``input`` and ``output`` keys (plus optional cache
        rates), or ``None`` if no exact-model rates could be determined.
    """
    return resolve_model_rates(
        provider,
        model_id,
        load_cache=_load_cache,
        fetch_models=_fetch_models,
        save_cache=_save_cache,
        strict=True,
    )


def get_model_limit_calibration(provider: str, model_id: str) -> ModelLimitCalibration:
    """Look up model token limits with typed calibration status.

    Resolution order:
    1. Fresh local cache → ``known_fresh`` / unknown / invalid metadata.
    2. Remote fetch when cache is missing or stale.
    3. Stale cache after remote failure → ``known_stale`` when usable.
    4. No usable source after remote failure → ``offline_no_cache``.

    Args:
        provider: Provider name (e.g. "openai", "anthropic").
        model_id: Model identifier (e.g. "gpt-4o", "claude-sonnet-4-5-20251020").

    Returns:
        A typed calibration result with status, provider caps, and source evidence.
    """
    cache_snapshot = _load_cache_snapshot()
    if cache_snapshot.is_fresh and cache_snapshot.data is not None:
        return calibrate_model_limits(
            provider=provider,
            model_id=model_id,
            snapshot=ModelLimitMetadataSnapshot(
                data=cache_snapshot.data,
                source="cache",
                source_timestamp=cache_snapshot.mtime,
                age_seconds=cache_snapshot.age_seconds,
            ),
        )

    try:
        data = _fetch_models()
        _save_cache(data)
        return calibrate_model_limits(
            provider=provider,
            model_id=model_id,
            snapshot=ModelLimitMetadataSnapshot(
                data=data,
                source="models.dev",
                source_timestamp=time.time(),
                age_seconds=0.0,
            ),
        )
    except Exception as exc:
        logger.warning(
            "models_fetch_failed_limits_unavailable",
            error=str(exc),
            provider=provider,
            model=model_id,
        )
        if cache_snapshot.data is not None:
            return calibrate_model_limits(
                provider=provider,
                model_id=model_id,
                snapshot=ModelLimitMetadataSnapshot(
                    data=cache_snapshot.data,
                    source="cache",
                    is_stale=True,
                    source_timestamp=cache_snapshot.mtime,
                    age_seconds=cache_snapshot.age_seconds,
                    error=str(exc),
                ),
            )
        return calibrate_model_limits(
            provider=provider,
            model_id=model_id,
            snapshot=ModelLimitMetadataSnapshot(
                data=None,
                source="models.dev",
                error=str(exc) or cache_snapshot.error,
            ),
        )


def get_model_limits(provider: str, model_id: str) -> ModelLimits | None:
    """Look up model token limits from models.dev.

    Compatibility wrapper around :func:`get_model_limit_calibration` for callers
    that still need the historical ``ModelLimits | None`` shape.
    """

    calibration = get_model_limit_calibration(provider, model_id)
    return calibration.limits


def get_cached_data() -> dict[str, Any] | None:
    """Return the raw cached models.dev JSON data.

    This is a no-frills accessor for API endpoints that want to expose
    the cache contents.  Returns ``None`` if no cache file exists.

    Returns:
        Parsed models.dev JSON, or None if not cached.
    """
    return _load_cache()


def refresh_models() -> dict[str, Any]:
    """Force-fetch fresh data from models.dev and update the cache.

    This is a manual refresh — it always fetches from the remote API
    regardless of cache state.

    Returns:
        The fetched models.dev data as a dict.  Returns an empty dict
        on failure (graceful degradation — never raises).
    """
    try:
        data = _fetch_models()
        _save_cache(data)
        return data
    except Exception as exc:
        logger.warning("models_refresh_failed", error=str(exc))
        return {}
