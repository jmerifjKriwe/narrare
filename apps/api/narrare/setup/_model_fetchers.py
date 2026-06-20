"""Provider model fetcher — delegates to ModelCatalogClient.

Extracted from provider_service.py per RULE-04 (file size limits).
All HTTP calls are handled by core/llm/model_listing.py (RULE-01b, RULE-08).
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from narrare.setup.base_schemas import AIProvider
from narrare.setup.provider_schemas import ProviderModel
from narrare_core.llm.model_listing import ModelCatalogClient, ModelCatalogEntry

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class FetchResult:
    """Result of fetching models from a provider catalog.

    Carries the model list plus a flag telling the caller whether the
    live catalog was reached or the bundled fallback was used. This flag
    is the signal that ``ProviderService.list_models`` needs to set
    ``ModelCatalogProvenance`` correctly (CR-AUFG-08-06).

    Attributes:
        models: The fetched (or fallback) model list.
        used_fallback: ``True`` if the live catalog was unreachable and
            the bundled fallback list was returned instead.
    """

    models: list[ProviderModel]
    used_fallback: bool


def _entry_to_model(entry: ModelCatalogEntry) -> ProviderModel:
    """Map a core ModelCatalogEntry to a setup-layer ProviderModel."""
    return ProviderModel(
        id=entry.id,
        name=entry.name,
        context_window=entry.context_window,
    )


async def fetch_models(
    provider: AIProvider,
    api_key: str,
    ollama_url: str,
    fallback_models: dict[AIProvider, list[ProviderModel]],
) -> FetchResult:
    """Fetch available models for a provider via ModelCatalogClient.

    Delegates all HTTP calls to ``ModelCatalogClient`` (RULE-01b, RULE-08).
    Falls back to hardcoded models on any error (RULE-11) and signals
    which path was taken via ``FetchResult.used_fallback`` so the caller
    can label the response provenance (CR-AUFG-08-06).

    Args:
        provider: The AI provider enum value.
        api_key: Provider API key (ignored for Ollama).
        ollama_url: Base URL for Ollama.
        fallback_models: Hardcoded fallback model lists per provider.

    Returns:
        ``FetchResult`` containing the model list and whether the
        fallback was used.
    """
    try:
        catalog = ModelCatalogClient()
        entries = await catalog.list_models(
            provider.value,
            api_key=api_key or None,
            base_url=ollama_url if provider == AIProvider.OLLAMA else None,
        )
        return FetchResult(
            models=[_entry_to_model(e) for e in entries],
            used_fallback=False,
        )
    except Exception:
        logger.warning(
            "model_fetch_failed_using_fallback",
            provider=provider,
            exc_info=True,
        )
        return FetchResult(
            models=fallback_models.get(provider, []),
            used_fallback=True,
        )
