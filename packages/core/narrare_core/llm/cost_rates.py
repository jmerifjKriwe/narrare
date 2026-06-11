"""
Model cost data from models.dev with local caching.

Provides per-model pricing lookup for cost estimation.
Cache is stored at ~/.narrare/cache/models_cache.json with 24h TTL.

Graceful degradation: if models.dev is unreachable, stale cache is used,
and if no cache exists, default rates are returned.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import httpx
import structlog

logger = structlog.get_logger(__name__)

MODELS_DEV_URL = "https://models.dev/api.json"
CACHE_DIR = Path.home() / ".narrare" / "cache"
CACHE_FILE = CACHE_DIR / "models_cache.json"

_DEFAULT_RATES: dict[str, dict[str, float]] = {
    # Fallback when model not found in models.dev
    # Values are {input: $/1M, output: $/1M}
    "openai": {"input": 10.0, "output": 30.0},
    "anthropic": {"input": 8.0, "output": 24.0},
    "google": {"input": 2.0, "output": 10.0},
    "groq": {"input": 0.5, "output": 1.0},
    "ollama": {"input": 0.0, "output": 0.0},
    "zai": {"input": 1.0, "output": 2.0},
    "openrouter": {"input": 5.0, "output": 15.0},
}


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ModelLimits:
    """Model token limits from models.dev.

    Represents the context window and max output tokens for a model.
    """

    context: int
    """Maximum context window size in tokens."""
    output: int
    """Maximum output tokens allowed."""


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


def _load_cache(cache_ttl: int = 86400) -> dict[str, Any] | None:
    """Load the local models.dev cache if it exists and is still fresh.

    Cache is considered valid if the file's mtime is less than
    *cache_ttl* seconds old.

    Returns:
        Parsed JSON data as dict, or None if no valid cache exists.
    """
    try:
        if not CACHE_FILE.exists():
            return None

        mtime = CACHE_FILE.stat().st_mtime
        age = time.time() - mtime
        if age > cache_ttl:
            logger.info("models_cache_expired", age_seconds=round(age))
            return None

        raw = CACHE_FILE.read_text(encoding="utf-8")
        data: dict[str, Any] = json.loads(raw)
        logger.debug("models_cache_loaded", file=str(CACHE_FILE))
        return data
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("models_cache_load_failed", error=str(exc))
        return None


def _fetch_models(*, timeout: float = 10.0) -> dict[str, Any]:
    """Fetch the models.dev dataset from the remote API.

    Args:
        timeout: Request timeout in seconds.

    Returns:
        Parsed JSON response as a dict.

    Raises:
        httpx.HTTPError: On connection or HTTP errors.
        json.JSONDecodeError: On invalid JSON response.
    """
    with httpx.Client(timeout=timeout) as client:
        response = client.get(MODELS_DEV_URL)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
    return data


def _save_cache(data: dict[str, Any]) -> None:
    """Save fetched models.dev data to the local cache file.

    Args:
        data: The models.dev JSON data to cache.
    """
    _ensure_cache_dir()
    try:
        CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("models_cache_saved", file=str(CACHE_FILE))
    except OSError as exc:
        logger.warning("models_cache_save_failed", error=str(exc))


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
    # 1. Load cache (or fetch if stale/missing)
    data = _load_cache()
    if data is None:
        try:
            data = _fetch_models()
            _save_cache(data)
        except Exception as exc:
            logger.warning(
                "models_fetch_failed_using_defaults",
                error=str(exc),
                provider=provider,
                model=model_id,
            )
            # Graceful degradation — try defaults
            return _DEFAULT_RATES.get(provider)

    # 2. Look up model_id in models.dev data
    # models.dev structure: {"models": {"<model_id>": {"cost": {"input": ..., "output": ...}}}}
    # data is guaranteed to be a dict here (None case handled above)
    models = cast("dict[str, Any]", data.get("models", {}))
    model_entry: dict[str, Any] = models.get(model_id, {})
    cost: dict[str, Any] = model_entry.get("cost", {})

    input_rate = cost.get("input")
    output_rate = cost.get("output")
    if input_rate is not None and output_rate is not None:
        try:
            return {
                "input": float(input_rate),
                "output": float(output_rate),
            }
        except TypeError, ValueError:
            pass

    # 3. Fall back to provider defaults
    fallback = _DEFAULT_RATES.get(provider)
    if fallback is not None:
        return fallback

    # 4. Nothing at all
    return None


def get_model_limits(provider: str, model_id: str) -> ModelLimits | None:
    """Look up model token limits from models.dev.

    Resolution order:
    1. Load from local cache (or fetch if cache is missing/expired)
    2. Look up ``model_id`` in the cached model data
    3. If nothing found, return ``None``

    Args:
        provider: Provider name (e.g. "openai", "anthropic").
        model_id: Model identifier (e.g. "gpt-4o", "claude-sonnet-4-5-20251020").

    Returns:
        A ``ModelLimits`` instance with ``context`` and ``output``,
        or ``None`` if no limits could be determined.
    """
    # 1. Load cache (or fetch if stale/missing)
    data = _load_cache()
    if data is None:
        try:
            data = _fetch_models()
            _save_cache(data)
        except Exception as exc:
            logger.warning(
                "models_fetch_failed_limits_unavailable",
                error=str(exc),
                provider=provider,
                model=model_id,
            )
            return None

    # 2. Look up model_id in models.dev data
    models = cast("dict[str, Any]", data.get("models", {}))
    model_entry: dict[str, Any] = models.get(model_id, {})
    limit: dict[str, Any] = model_entry.get("limit", {})

    context_val = limit.get("context")
    output_val = limit.get("output")
    if context_val is not None and output_val is not None:
        try:
            return ModelLimits(
                context=int(context_val),
                output=int(output_val),
            )
        except TypeError, ValueError:
            pass

    # 3. Nothing found
    return None


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
