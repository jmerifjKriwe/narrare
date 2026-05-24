"""Router for model data refresh endpoint.

Provides a POST endpoint to manually refresh the models.dev cache
and return a diff summary between old and new model sets.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

from narrare_core.llm.cost_rates import get_cached_data, refresh_models

router = APIRouter(tags=["models"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_model_ids(data: dict[str, Any] | None) -> set[str]:
    """Extract all model IDs from the models.dev JSON structure.

    The models.dev response has the shape::

        { "models": { "<model_id>": { ... } } }

    Args:
        data: The models.dev JSON data, or ``None`` if no cache exists.

    Returns:
        A set of model ID strings, or an empty set if data is ``None``.

    Example:
        >>> _extract_model_ids({"models": {"gpt-4o": {}, "claude-3": {}}})
        {'gpt-4o', 'claude-3'}
        >>> _extract_model_ids(None)
        set()
    """
    if data is None:
        return set()
    models: dict[str, Any] = data.get("models", {})
    return set(models.keys())


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/models/refresh")
async def refresh_model_data() -> dict[str, Any]:
    """Fetch latest model data from models.dev.

    Invalidates the local cache and fetches fresh data from models.dev.
    Returns a diff summary between the old and new model sets.

    The response never carries a 500 status — on failure the endpoint
    returns ``{"status": "error", "message": "...", "cached_at": "..."}``.

    Returns:
        A dict with keys:
        - ``status``: ``"ok"`` on success, ``"error"`` on failure.
        - ``new_models``: list of model IDs new in the refresh.
        - ``removed_models``: list of model IDs no longer present.
        - ``total_models``: total count of models after refresh.
        - ``cached_at``: ISO-8601 timestamp of the refresh.
    """
    # Capture old data for diff computation (before refresh invalidates it).
    old_data = get_cached_data()

    # Fetch fresh data — refresh_models() is synchronous, run in thread pool.
    loop = asyncio.get_running_loop()
    new_data = await loop.run_in_executor(None, refresh_models)

    cached_at = datetime.now(UTC).isoformat()

    if not new_data:
        return {
            "status": "error",
            "message": "Failed to fetch fresh model data from models.dev",
            "cached_at": cached_at,
        }

    old_model_ids: set[str] = _extract_model_ids(old_data) if old_data else set()
    new_model_ids: set[str] = _extract_model_ids(new_data)

    return {
        "status": "ok",
        "new_models": sorted(new_model_ids - old_model_ids),
        "removed_models": sorted(old_model_ids - new_model_ids),
        "total_models": len(new_model_ids),
        "cached_at": cached_at,
    }
