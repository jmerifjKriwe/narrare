"""models.dev pricing lookup helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import structlog

logger = structlog.get_logger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable

DEFAULT_RATES: dict[str, dict[str, float]] = {
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


def resolve_model_rates(
    provider: str,
    model_id: str,
    *,
    load_cache: Callable[[], dict[str, Any] | None],
    fetch_models: Callable[[], dict[str, Any]],
    save_cache: Callable[[dict[str, Any]], None],
    strict: bool = False,
) -> dict[str, float] | None:
    """Resolve per-model pricing from cache/remote metadata with defaults.

    With ``strict=True`` only exact-model metadata rates are accepted:
    unknown models and fetch failures return ``None`` instead of falling
    back to ``DEFAULT_RATES``.
    """

    data = load_cache()
    if data is None:
        try:
            data = fetch_models()
            save_cache(data)
        except Exception as exc:
            logger.warning(
                "models_fetch_failed_using_defaults",
                error=str(exc),
                provider=provider,
                model=model_id,
            )
            if strict:
                return None
            return DEFAULT_RATES.get(provider)

    rates = _rates_from_metadata(provider, model_id, data)
    if rates is not None:
        return rates

    if not strict:
        return DEFAULT_RATES.get(provider)
    return None


def _rates_from_metadata(
    provider: str,
    model_id: str,
    data: dict[str, Any],
) -> dict[str, float] | None:
    models = cast("dict[str, Any]", data.get("models", {}))
    model_entry: dict[str, Any] = models.get(model_id, {})
    cost: dict[str, Any] = model_entry.get("cost", {})

    input_rate = cost.get("input")
    output_rate = cost.get("output")
    if input_rate is None or output_rate is None:
        return None
    try:
        rates: dict[str, float] = {
            "input": float(input_rate),
            "output": float(output_rate),
        }
        cache_read = cost.get("cache_read")
        if cache_read is not None:
            rates["cache_read"] = float(cache_read)
        cache_write = cost.get("cache_write")
        if cache_write is not None:
            rates["cache_write"] = float(cache_write)
        return rates
    except (TypeError, ValueError) as exc:
        logger.warning(
            "models_cost_metadata_invalid",
            error=str(exc),
            provider=provider,
            model=model_id,
        )
        return None
