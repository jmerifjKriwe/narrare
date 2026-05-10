"""
Provider service — fetches available models and validates API connections.

Each provider gets a real test call during Step 4 validation.
Model lists are fetched from provider APIs and cached in Redis.
"""

from __future__ import annotations

import httpx
import structlog

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
    ) -> bool:
        """
        Make a minimal real API call to verify the provider + key + model work.

        Args:
            provider: The AI provider.
            api_key: Provider API key.
            model: Model ID to test.
            ollama_url: Ollama base URL.

        Returns:
            True if the connection works, False otherwise.
        """
        try:
            await self._test_call(provider, api_key, model, ollama_url)
            logger.info("provider_validation_success", provider=provider.value, model=model)
            return True
        except Exception as e:
            logger.warning(
                "provider_validation_failed",
                provider=provider.value,
                model=model,
                error=str(e),
            )
            return False

    async def _fetch_models(
        self,
        provider: AIProvider,
        api_key: str,
        ollama_url: str,
    ) -> list[ProviderModel]:
        """Fetch models from provider API."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            if provider == AIProvider.ANTHROPIC:
                return await self._fetch_anthropic_models(client, api_key)
            if provider == AIProvider.OPENAI:
                return await self._fetch_openai_models(client, api_key)
            if provider == AIProvider.OLLAMA:
                return await self._fetch_ollama_models(client, ollama_url)
            if provider == AIProvider.OPENROUTER:
                return await self._fetch_openrouter_models(client, api_key)
            if provider == AIProvider.ZAI:
                return await self._fetch_zai_models(client, api_key)
        # For providers without model list API, use fallback
        return _FALLBACK_MODELS.get(provider, [])

    async def _fetch_anthropic_models(
        self, client: httpx.AsyncClient, api_key: str
    ) -> list[ProviderModel]:
        response = await client.get(
            # narrare: allow-direct-llm reason="Setup-phase provider validation and model listing"
            "https://api.anthropic.com/v1/models",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        )
        response.raise_for_status()
        data = response.json()
        return [
            ProviderModel(
                id=m["id"],
                name=m.get("display_name", m["id"]),
                context_window=m.get("context_window"),
            )
            for m in data.get("data", [])
            if "claude" in m["id"].lower()
        ]

    async def _fetch_openai_models(
        self, client: httpx.AsyncClient, api_key: str
    ) -> list[ProviderModel]:
        response = await client.get(
            # narrare: allow-direct-llm reason="Setup-phase provider validation and model listing"
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response.raise_for_status()
        data = response.json()
        # Filter to chat-capable models only
        chat_models = [
            m
            for m in data.get("data", [])
            if any(k in m["id"] for k in ("gpt-4", "gpt-3.5", "o1", "o3"))
        ]
        return [ProviderModel(id=m["id"], name=m["id"]) for m in chat_models]

    async def _fetch_ollama_models(
        self, client: httpx.AsyncClient, ollama_url: str
    ) -> list[ProviderModel]:
        base = ollama_url.rstrip("/")
        response = await client.get(f"{base}/api/tags")
        response.raise_for_status()
        data = response.json()
        return [
            ProviderModel(
                id=m["name"],
                name=m["name"],
                context_window=m.get("details", {}).get("context_length"),
            )
            for m in data.get("models", [])
        ]

    async def _fetch_openrouter_models(
        self, client: httpx.AsyncClient, api_key: str
    ) -> list[ProviderModel]:
        response = await client.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response.raise_for_status()
        data = response.json()
        return [
            ProviderModel(
                id=m["id"],
                name=m.get("name", m["id"]),
                context_window=m.get("context_length"),
            )
            for m in data.get("data", [])
        ][:30]  # Limit to 30 most relevant

    async def _fetch_zai_models(
        self, client: httpx.AsyncClient, api_key: str
    ) -> list[ProviderModel]:
        response = await client.get(
            "https://api.z.ai/api/paas/v4/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response.raise_for_status()
        data = response.json()
        models = data.get("data", [])
        return [ProviderModel(id=m["id"], name=m.get("id", m["id"])) for m in models]

    async def _test_call(
        self,
        provider: AIProvider,
        api_key: str,
        model: str,
        ollama_url: str,
    ) -> None:
        """Make a minimal API call to verify the connection."""
        # Use pydantic-ai for the test call — goes through the gateway pattern
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

        provider_name = provider.value
        factory = get_provider(provider_name)
        pydantic_model = factory(model)

        agent = Agent(pydantic_model, result_type=str)  # type: ignore[call-arg]
        # Minimal prompt — just verify the connection works
        result = await agent.run("Reply with the single word: OK")

        if not str(result):
            raise ValueError("Empty response from provider")
