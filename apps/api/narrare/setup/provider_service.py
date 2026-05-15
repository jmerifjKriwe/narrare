"""
Provider service — fetches available models and validates API connections.

Each provider gets a real test call during Step 4 validation.
Model lists are fetched from provider APIs and cached in Redis.
"""

from __future__ import annotations

import structlog

from narrare.setup._model_fetchers import fetch_models
from narrare.setup.schemas import (
    AIProvider,
    AvailableModelsResponse,
    ProviderModel,
)

logger = structlog.get_logger(__name__)

# Fallback model lists when API is unavailable
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
        ollama_url: str = "http://localhost:11434",
    ) -> AvailableModelsResponse:
        """
        Fetch available models for a provider.

        Falls back to a hardcoded list if the API is unreachable.

        Args:
            provider: The AI provider.
            api_key: Provider API key (ignored for Ollama).
            ollama_url: Base URL for Ollama (only used when provider==OLLAMA).

        Returns:
            AvailableModelsResponse with model list.
        """
        try:
            models = await self._fetch_models(provider, api_key, ollama_url)
        except Exception as e:
            logger.warning(
                "provider_model_fetch_failed",
                provider=provider.value,
                error=str(e),
                fallback=True,
            )
            models = _FALLBACK_MODELS.get(provider, [])

        return AvailableModelsResponse(provider=provider, models=models)

    async def validate_connection(
        self,
        provider: AIProvider,
        api_key: str,
        model: str,
        ollama_url: str = "http://localhost:11434",
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
    ) -> list[ProviderModel]:
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
        """Make a minimal API call to verify the connection."""
        import os

        from narrare_core.llm._providers.registry import get as get_provider

        # Temporarily set the API key for this call
        env_map = {
            AIProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
            AIProvider.OPENAI: "OPENAI_API_KEY",
            AIProvider.GOOGLE: "GOOGLE_API_KEY",
            AIProvider.GROQ: "GROQ_API_KEY",
            AIProvider.OPENROUTER: "OPENROUTER_API_KEY",
            AIProvider.ZAI: "ZAI_API_KEY",
        }

        if provider == AIProvider.OLLAMA:
            os.environ["OLLAMA_BASE_URL"] = ollama_url
        elif provider in env_map:
            os.environ[env_map[provider]] = api_key

        # narrare: allow-direct-llm reason="Setup-phase provider validation and model listing"
        from pydantic_ai import Agent

        if provider == AIProvider.ZAI and zai_endpoint == "coding":
            from narrare_core.llm._providers.zai import make_zai_coding

            pydantic_model = make_zai_coding(model)
        else:
            provider_name = provider.value
            factory = get_provider(provider_name)
            pydantic_model = factory(model)

        agent = Agent(pydantic_model, output_type=str)
        # Minimal prompt — just verify the connection works
        result = await agent.run("Reply with the single word: OK")

        if not str(result):
            raise ValueError("Empty response from provider")
