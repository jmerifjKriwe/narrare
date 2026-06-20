"""models.dev metadata fetch/cache helpers.

Kept separate from ``cost_rates.py`` so pricing lookup and calibration policy do
not grow into one mixed-responsibility module.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import httpx
import structlog

logger = structlog.get_logger(__name__)

if TYPE_CHECKING:
    from pathlib import Path


CACHE_TTL: int = 86400
"""Default TTL for the local models.dev metadata cache (seconds = 24h).

Change requires verifying freshness requirements for model metadata
(pricing, limits) used by cost estimation and calibration.
"""

FETCH_TIMEOUT: float = 10.0
"""Default HTTP timeout for fetching the models.dev dataset (seconds).

Change requires verifying that the remote API responds within the new
limit under normal network conditions.
"""


@dataclass(frozen=True, slots=True)
class ModelMetadataCacheSnapshot:
    """Cached models.dev data with freshness evidence."""

    data: dict[str, Any] | None
    mtime: float | None
    age_seconds: float | None
    is_fresh: bool
    error: str | None = None


def ensure_cache_dir(cache_dir: Path) -> Path:
    """Create the cache directory if it does not exist."""

    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def load_cache_snapshot(
    cache_file: Path,
    *,
    cache_ttl: int = CACHE_TTL,
) -> ModelMetadataCacheSnapshot:
    """Load cache data with freshness evidence."""

    try:
        if not cache_file.exists():
            return ModelMetadataCacheSnapshot(
                data=None,
                mtime=None,
                age_seconds=None,
                is_fresh=False,
            )

        mtime = cache_file.stat().st_mtime
        age = time.time() - mtime
        raw = cache_file.read_text(encoding="utf-8")
        data = coerce_metadata_root(json.loads(raw))
        if age > cache_ttl:
            logger.info("models_cache_expired", age_seconds=round(age))
            return ModelMetadataCacheSnapshot(
                data=data,
                mtime=mtime,
                age_seconds=age,
                is_fresh=False,
            )
        logger.debug("models_cache_loaded", file=str(cache_file))
        return ModelMetadataCacheSnapshot(
            data=data,
            mtime=mtime,
            age_seconds=age,
            is_fresh=True,
        )
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("models_cache_load_failed", error=str(exc))
        return ModelMetadataCacheSnapshot(
            data=None,
            mtime=None,
            age_seconds=None,
            is_fresh=False,
            error=str(exc),
        )


def fetch_models(url: str, *, timeout: float = FETCH_TIMEOUT) -> dict[str, Any]:
    """Fetch and parse the models.dev dataset."""

    with httpx.Client(timeout=timeout) as client:
        response = client.get(url)
        response.raise_for_status()
        return coerce_metadata_root(response.json())


def save_cache(cache_dir: Path, cache_file: Path, data: dict[str, Any]) -> None:
    """Persist fetched models.dev metadata to disk."""

    ensure_cache_dir(cache_dir)
    try:
        cache_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("models_cache_saved", file=str(cache_file))
    except OSError as exc:
        logger.warning("models_cache_save_failed", error=str(exc))


def coerce_metadata_root(value: object) -> dict[str, Any]:
    """Return a dict root so malformed metadata becomes typed invalid evidence."""

    if isinstance(value, dict):
        return cast("dict[str, Any]", value)
    return {"_invalid_metadata_root": value}
