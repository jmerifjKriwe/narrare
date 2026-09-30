"""
Provider service — fetches available models and validates API connections.

Each provider gets a real test call during Step 4 validation.
Model lists are fetched from provider APIs and cached locally.
"""

from __future__ import annotations

import structlog

from narrare.setup._model_fetchers import FetchResult, fetch_models
from narrare.setup.base_schemas import AIProvider
from narrare.setup.constants import (
    FALLBACK_CATALOG_LAST_REVIEWED,
    FALLBACK_CATALOG_SOURCE,
    LIVE_CATALOG_SOURCE,
    OLLAMA_DEFAULT_URL,
)
from narrare.setup.provider_schemas import (
    AvailableModelsResponse,
    ModelCatalogProvenance,
    ProviderModel,
)

logger = structlog.get_logger(__name__)

# Fallback model lists when API is unavailable
#
# Source: Provider docs (2025-10)
# Freshness: Checked 2025-10; update FALLBACK_CATALOG_LAST_REVIEWED when refreshing
_FALLBACK_MODELS: dict[AIProvider, list[ProviderModel]] = {
    AIProvider.ANTHROPIC: [
        ProviderModel(id="claude-opus-4-5-20251101", name="Claude Opus 4.5", context_window=200000),
        ProviderModel(
            id="claude-sonnet-4-5-20251020", name="Claude Sonnet 4.5", context_window=200000
        ),
        ProviderModel(
            id="claude-haiku-3-5-20241022", name="Claude Haiku 3.5", context_window=200000
        ),
    ],
    AIProvider.OPENAI: [
        ProviderModel(id="gpt-4o", name="GPT-4o", context_window=128000),
        ProviderModel(id="gpt-4o-mini", name="GPT-4o Mini", context_window=128000),
        ProviderModel(id="o3-mini", name="o3-mini", context_window=200000),
    ],
    AIProvider.GOOGLE: [
        ProviderModel(id="gemini-2.0-flash", name="Gemini 2.0 Flash", context_window=1000000),
        ProviderModel(id="gemini-1.5-pro", name="Gemini 1.5 Pro", context_window=2000000),
    ],
    AIProvider.GROQ: [
        ProviderModel(id="llama-3.3-70b-versatile", name="Llama 3.3 70B", context_window=128000),
        ProviderModel(id="mixtral-8x7b-32768", name="Mixtral 8x7B", context_window=32768),
    ],
    AIProvider.OPENROUTER: [
        ProviderModel(
            id="anthropic/claude-sonnet-4-5",
            name="Claude Sonnet 4.5 (OR)",
            context_window=200000,
        ),
        ProviderModel(id="openai/gpt-4o", name="GPT-4o (OR)", context_window=128000),
        ProviderModel(
            id="google/gemini-2.0-flash",
            name="Gemini 2.0 Flash (OR)",
            context_window=1000000,
        ),
    ],
    AIProvider.ZAI: [
        ProviderModel(id="glm-z1-32b", name="GLM-Z1 32B", context_window=128000),
        ProviderModel(id="glm-4-flash", name="GLM-4 Flash", context_window=128000),
        ProviderModel(id="glm-5.3-flash", name="GLM-5.3 Flash", context_window=128000),
    ],
    AIProvider.OLLAMA: [
        ProviderModel(id="llama3.2", name="Llama 3.2", context_window=128000),
        ProviderModel(id="mistral", name="Mistral 7B", context_window=32768),
        ProviderModel(id="qwen2.5", name="Qwen 2.5", context_window=128000),
    ],
}


class ProviderService:
    """Fetches model lists and validates provider API connections."""

    async def list_models(
        self,
        provider: AIProvider,
        api_key: str,
        ollama_url: str = OLLAMA_DEFAULT_URL,
    ) -> AvailableModelsResponse:
        """
        Fetch available models for a provider.

        Falls back to a hardcoded list if the API is unreachable and
        labels the response provenance so clients can distinguish
        live-fetched models from stale bundled fallback (CR-AUFG-08-06).

        Args:
            provider: The AI provider.
            api_key: Provider API key (ignored for Ollama).
            ollama_url: Base URL for Ollama (only used when provider==OLLAMA).

        Returns:
            AvailableModelsResponse with model list and provenance.
        """
        try:
            result = await self._fetch_models(provider, api_key, ollama_url)
        except Exception as e:
            logger.warning(
                "provider_model_fetch_failed",
                provider=provider.value,
                error=str(e),
                fallback=True,
            )
            result = FetchResult(
                models=_FALLBACK_MODELS.get(provider, []),
                used_fallback=True,
            )

        provenance = (
            ModelCatalogProvenance(
                source=FALLBACK_CATALOG_SOURCE,
                last_reviewed=FALLBACK_CATALOG_LAST_REVIEWED,
            )
            if result.used_fallback
            else ModelCatalogProvenance(source=LIVE_CATALOG_SOURCE)
        )
        return AvailableModelsResponse(
            provider=provider,
            models=result.models,
            provenance=provenance,
        )

    async def validate_connection(
        self,
        provider: AIProvider,
        api_key: str,
        model: str,
        ollama_url: str = OLLAMA_DEFAULT_URL,
        zai_endpoint: str = "general",
    ) -> str | None:
        """
        Make a minimal real API call to verify the provider + key + model work.

        If *model* is the placeholder ``"test"``, dynamically resolves to the
        first available model from the provider's model list.

        Args:
            provider: The AI provider.
            api_key: Provider API key.
            model: Model ID to test, or ``"test"`` for dynamic resolution.
            ollama_url: Ollama base URL.
            zai_endpoint: Z.AI endpoint variant — "general" or "coding".

        Returns:
            None if the connection works, or the error message string if it fails.
        """
        resolved_model = model
        if model == "test":
            try:
                models_response = await self.list_models(provider, api_key, ollama_url)
                if models_response.models:
                    resolved_model = models_response.models[0].id
                    logger.info(
                        "resolved_test_model",
                        provider=provider.value,
                        resolved_model=resolved_model,
                    )
                else:
                    msg = (
                        "Keine Modelle gefunden — prüfen Sie Ihren API-Key"
                        " und Ihre Netzwerkverbindung."
                    )
                    logger.warning("no_models_available", provider=provider.value)
                    return msg
            except Exception as e:
                msg = f"Modellliste konnte nicht abgerufen werden: {e}"
                logger.warning(
                    "model_list_fetch_failed",
                    provider=provider.value,
                    error=str(e),
                )
                return msg

        try:
            await self._test_call(provider, api_key, resolved_model, ollama_url, zai_endpoint)
            logger.info(
                "provider_validation_success",
                provider=provider.value,
                model=resolved_model,
            )
            return None
        except Exception as e:
            error_msg = str(e)
            logger.warning(
                "provider_validation_failed",
                provider=provider.value,
                model=resolved_model,
                error=error_msg,
            )
            return error_msg

    async def _fetch_models(
        self,
        provider: AIProvider,
        api_key: str,
        ollama_url: str,
    ) -> FetchResult:
        """Delegate to _model_fetchers.fetch_models."""
        return await fetch_models(provider, api_key, ollama_url, _FALLBACK_MODELS)

    async def _test_call(
        self,
        provider: AIProvider,
        api_key: str,
        model: str,
        ollama_url: str,
        zai_endpoint: str = "general",
    ) -> None:
        """
        Make a minimal API call to verify the connection.

        Credentials are passed per-request to the provider factory
        (``factory(model, api_key=...)``) — environment variables are
        never mutated. This is required because ``get_core_settings()``
        is lru-cached (ADR-071) and instantiated at startup: env writes
        after startup are invisible to it, so per-user keys from the
        setup wizard must travel through the factory's documented
        pass-through parameters.
        """
        # narrare: allow-agent reason="Setup-phase provider validation (ADR-015)"
        from pydantic_ai import Agent

        from narrare_core.llm._providers.registry import get as get_provider

        if provider == AIProvider.ZAI and zai_endpoint == "coding":
            from narrare_core.llm._providers.zai import make_zai_coding

            pydantic_model = make_zai_coding(model, api_key=api_key)
        elif provider == AIProvider.OLLAMA:
            provider_name = provider.value
            factory = get_provider(provider_name)
            # Ollama takes its endpoint via base_url (api_key is ignored there).
            pydantic_model = factory(model, base_url=ollama_url)
        else:
            provider_name = provider.value
            factory = get_provider(provider_name)
            pydantic_model = factory(model, api_key=api_key)

        agent = Agent(  # narrare: allow-agent reason="Setup-phase validation (ADR-015)"
            pydantic_model, output_type=str
        )
        # Minimal prompt — just verify the connection works
        result = await agent.run(  # narrare: allow-agent reason="Setup-phase validation (ADR-015)"
            "Reply with the single word: OK"
        )  # narrare: allow-agent reason="Setup-phase validation (ADR-015)"

        if not str(result):
            raise ValueError("Empty response from provider")
