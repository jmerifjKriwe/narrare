"""
Provider model fetcher functions — one per provider.

Extracted from provider_service.py per RULE-04 (file size limits).
Each function takes an httpx.AsyncClient and provider-specific credentials,
returns a list of ProviderModel.
"""

from __future__ import annotations

import httpx

from narrare.setup.base_schemas import AIProvider
from narrare.setup.provider_schemas import ProviderModel


async def fetch_models(
    provider: AIProvider,
    api_key: str,
    ollama_url: str,
    fallback_models: dict[AIProvider, list[ProviderModel]],
) -> list[ProviderModel]:
    """Dispatch to the correct provider fetcher.

    Args:
        provider: The AI provider enum value.
        api_key: Provider API key (ignored for Ollama).
        ollama_url: Base URL for Ollama.
        fallback_models: Hardcoded fallback model lists per provider.

    Returns:
        List of ProviderModel for the given provider.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        if provider == AIProvider.ANTHROPIC:
            return await _fetch_anthropic_models(client, api_key)
        if provider == AIProvider.OPENAI:
            return await _fetch_openai_models(client, api_key)
        if provider == AIProvider.OLLAMA:
            return await _fetch_ollama_models(client, ollama_url)
        if provider == AIProvider.OPENROUTER:
            return await _fetch_openrouter_models(client, api_key)
        if provider == AIProvider.ZAI:
            return await _fetch_zai_models(client, api_key)
        if provider == AIProvider.GOOGLE:
            return await _fetch_google_models(client, api_key)
        if provider == AIProvider.GROQ:
            return await _fetch_groq_models(client, api_key)
    # For providers without a dedicated fetcher, use fallback
    return fallback_models.get(provider, [])


async def _fetch_anthropic_models(client: httpx.AsyncClient, api_key: str) -> list[ProviderModel]:
    """Fetch available Anthropic models."""
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


async def _fetch_openai_models(client: httpx.AsyncClient, api_key: str) -> list[ProviderModel]:
    """Fetch available OpenAI models (chat-capable only)."""
    response = await client.get(
        # narrare: allow-direct-llm reason="Setup-phase provider validation and model listing"
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    response.raise_for_status()
    data = response.json()
    chat_models = [
        m
        for m in data.get("data", [])
        if any(k in m["id"] for k in ("gpt-4", "gpt-3.5", "o1", "o3"))
    ]
    return [ProviderModel(id=m["id"], name=m["id"]) for m in chat_models]


async def _fetch_ollama_models(client: httpx.AsyncClient, ollama_url: str) -> list[ProviderModel]:
    """Fetch locally available Ollama models."""
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


async def _fetch_openrouter_models(client: httpx.AsyncClient, api_key: str) -> list[ProviderModel]:
    """Fetch available OpenRouter models (limited to 30)."""
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
    ][:30]


async def _fetch_zai_models(client: httpx.AsyncClient, api_key: str) -> list[ProviderModel]:
    """Fetch available Z.AI models."""
    response = await client.get(
        "https://api.z.ai/api/paas/v4/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    response.raise_for_status()
    data = response.json()
    models = data.get("data", [])
    return [ProviderModel(id=m["id"], name=m.get("id", m["id"])) for m in models]


async def _fetch_google_models(client: httpx.AsyncClient, api_key: str) -> list[ProviderModel]:
    """Fetch available Google AI Studio models (generateContent only).

    The Google API returns models with a ``models/`` prefix in the name field.
    We strip this prefix to get the clean model ID.

    Args:
        client: Shared httpx async client.
        api_key: Google AI Studio API key.

    Returns:
        List of ProviderModel entries for generateContent-capable models.
    """
    response = await client.get(
        # narrare: allow-direct-llm reason="Setup-phase provider validation and model listing"
        f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
    )
    response.raise_for_status()
    data = response.json()
    models: list[ProviderModel] = []
    for m in data.get("models", []):
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" not in methods:
            continue
        raw_name: str = m.get("name", "")
        model_id = raw_name.removeprefix("models/")
        models.append(
            ProviderModel(
                id=model_id,
                name=m.get("displayName", model_id),
                context_window=m.get("inputTokenLimit"),
            )
        )
    return models


async def _fetch_groq_models(client: httpx.AsyncClient, api_key: str) -> list[ProviderModel]:
    """Fetch available Groq models (OpenAI-compatible endpoint).

    Args:
        client: Shared httpx async client.
        api_key: Groq API key.

    Returns:
        List of ProviderModel entries from Groq.
    """
    response = await client.get(
        # narrare: allow-direct-llm reason="Setup-phase provider validation and model listing"
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    response.raise_for_status()
    data = response.json()
    return [ProviderModel(id=m["id"], name=m["id"]) for m in data.get("data", [])]
