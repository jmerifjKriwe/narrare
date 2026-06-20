"""Provider model catalog adapter.

Lists available models from LLM provider REST APIs (Anthropic, OpenAI,
Ollama, Google, Groq, OpenRouter, Z.AI).  This module is the **only**
place in core/ that makes HTTP calls to provider catalog endpoints —
CONSTRAINTS.md RULE-01b and RULE-08.

Catalog queries are read-only GET requests; they do **not** invoke LLM
inference.  For inference, see ``gateway.py`` (RULE-01b).

Contract: ``ModelCatalogProtocol`` in ``contracts.py`` (RULE-03).
"""

from __future__ import annotations

import httpx
import structlog
from pydantic import BaseModel

__all__ = [
    "SUPPORTED_CATALOG_PROVIDERS",
    "ModelCatalogClient",
    "ModelCatalogEntry",
    "ModelCatalogError",
]

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ModelCatalogEntry(BaseModel):
    """A model available from a provider's catalog."""

    id: str
    name: str
    context_window: int | None = None


class ModelCatalogError(Exception):
    """Raised when a provider catalog API call fails.

    Wraps network errors, unexpected HTTP status codes, and response
    parsing failures with a provider-annotated message.
    """

    def __init__(self, provider: str, detail: str) -> None:
        self.provider = provider
        self.detail = detail
        super().__init__(f"Model catalog error for {provider}: {detail}")


# ---------------------------------------------------------------------------
# Provider registry (internal)
# ---------------------------------------------------------------------------

SUPPORTED_CATALOG_PROVIDERS: frozenset[str] = frozenset(
    {"anthropic", "openai", "ollama", "google", "groq", "openrouter", "zai"}
)

# OpenRouter returns hundreds of models; cap to keep the UI usable.
# The default (30) is configured in ModelCatalogClient.__init__.

CATALOG_TIMEOUT: float = 10.0
"""Default HTTP timeout for provider catalog API calls (seconds).

Affected by:
  * ``ModelCatalogClient`` — provider catalog queries
  * ``_fetch_models`` / ``fetch_models`` — models.dev dataset fetch

Change requires verifying that local-network providers (Ollama, local
OpenAI-compatible proxies) can still respond within the new limit.
"""

OPENROUTER_MAX_MODELS: int = 30
"""Default cap on the number of OpenRouter catalog entries returned.

OpenRouter returns hundreds of models. This cap keeps the provider
model listing UI responsive. Change requires verifying the cap does
not hide production-relevant models from the UI.
"""

# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class ModelCatalogClient:
    """Concrete implementation of ``ModelCatalogProtocol``.

    Uses ``httpx.AsyncClient`` to query provider REST APIs.  Provider
    names are plain strings — there is no dependency on ``apps/``
    (RULE-07).

    Usage::

        client = ModelCatalogClient()
        models = await client.list_models("openai", api_key="sk-...")
    """

    def __init__(
        self,
        *,
        catalog_timeout: float = CATALOG_TIMEOUT,
        openrouter_max_models: int = OPENROUTER_MAX_MODELS,
    ) -> None:
        self._catalog_timeout = catalog_timeout
        self._openrouter_max_models = openrouter_max_models

    # -- public API ---------------------------------------------------------

    async def list_models(
        self,
        provider: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> list[ModelCatalogEntry]:
        """List available models for a given provider.

        Parameters
        ----------
        provider:
            Provider name (e.g. ``"anthropic"``, ``"openai"``, ``"ollama"``).
        api_key:
            Provider API key.  Required for cloud providers; ``None`` for Ollama.
        base_url:
            Optional base URL override (e.g. Ollama URL, custom endpoint).

        Returns
        -------
        list[ModelCatalogEntry]
            Available models from the provider's catalog.

        Raises
        ------
        ModelCatalogError
            If the provider is unsupported, the API is unreachable, or
            returns an unexpected response.
        """
        normalized = provider.lower()
        if normalized not in SUPPORTED_CATALOG_PROVIDERS:
            raise ModelCatalogError(
                provider,
                f"Unsupported provider. Supported: {sorted(SUPPORTED_CATALOG_PROVIDERS)}",
            )

        try:
            async with httpx.AsyncClient(timeout=self._catalog_timeout) as client:
                return await self._dispatch(client, normalized, api_key, base_url)
        except ModelCatalogError:
            raise
        except httpx.HTTPStatusError as exc:
            raise ModelCatalogError(
                provider,
                f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            ) from exc
        except httpx.RequestError as exc:
            raise ModelCatalogError(provider, f"Network error: {exc}") from exc
        except Exception as exc:
            logger.warning(
                "model_catalog_unexpected_error",
                provider=provider,
                error=str(exc),
            )
            raise ModelCatalogError(provider, f"Unexpected error: {exc}") from exc

    # -- dispatch -----------------------------------------------------------

    async def _dispatch(
        self,
        client: httpx.AsyncClient,
        provider: str,
        api_key: str | None,
        base_url: str | None,
    ) -> list[ModelCatalogEntry]:
        """Route to the correct provider fetcher."""
        if provider == "anthropic":
            return await self._fetch_anthropic(client, api_key)
        if provider == "openai":
            return await self._fetch_openai(client, api_key)
        if provider == "ollama":
            return await self._fetch_ollama(client, base_url)
        if provider == "google":
            return await self._fetch_google(client, api_key)
        if provider == "groq":
            return await self._fetch_groq(client, api_key)
        if provider == "openrouter":
            return await self._fetch_openrouter(client, api_key)
        if provider == "zai":
            return await self._fetch_zai(client, api_key)

        # Should never reach here (guarded by list_models), but defensive.
        raise ModelCatalogError(provider, "No fetcher registered")

    # -- Anthropic ----------------------------------------------------------

    async def _fetch_anthropic(
        self,
        client: httpx.AsyncClient,
        api_key: str | None,
    ) -> list[ModelCatalogEntry]:
        """Fetch available Anthropic models.

        Filters to only include Claude models (consistent with the
        previous implementation in ``_model_fetchers.py``).
        """
        response = await client.get(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": api_key or "",
                "anthropic-version": "2023-06-01",
            },
        )
        response.raise_for_status()
        data = response.json()
        return [
            ModelCatalogEntry(
                id=m["id"],
                name=m.get("display_name", m["id"]),
                context_window=m.get("context_window"),
            )
            for m in data.get("data", [])
            if "claude" in m["id"].lower()
        ]

    # -- OpenAI -------------------------------------------------------------

    async def _fetch_openai(
        self,
        client: httpx.AsyncClient,
        api_key: str | None,
    ) -> list[ModelCatalogEntry]:
        """Fetch available OpenAI models (chat-capable only).

        Filters to models whose ID contains known chat model families.
        """
        response = await client.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response.raise_for_status()
        data = response.json()
        chat_keywords = ("gpt-4", "gpt-3.5", "o1", "o3")
        return [
            ModelCatalogEntry(id=m["id"], name=m["id"])
            for m in data.get("data", [])
            if any(k in m["id"] for k in chat_keywords)
        ]

    # -- Ollama -------------------------------------------------------------

    async def _fetch_ollama(
        self,
        client: httpx.AsyncClient,
        base_url: str | None,
    ) -> list[ModelCatalogEntry]:
        """Fetch locally available Ollama models.

        Ollama has no authentication — it queries the local server.
        """
        base = (base_url or "http://localhost:11434").rstrip("/")
        response = await client.get(f"{base}/api/tags")
        response.raise_for_status()
        data = response.json()
        return [
            ModelCatalogEntry(
                id=m["name"],
                name=m["name"],
                context_window=m.get("details", {}).get("context_length"),
            )
            for m in data.get("models", [])
        ]

    # -- Google -------------------------------------------------------------

    async def _fetch_google(
        self,
        client: httpx.AsyncClient,
        api_key: str | None,
    ) -> list[ModelCatalogEntry]:
        """Fetch available Google AI Studio models (generateContent only).

        The Google API returns model names with a ``models/`` prefix
        which is stripped to produce clean model IDs.
        """
        response = await client.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
        )
        response.raise_for_status()
        data = response.json()
        entries: list[ModelCatalogEntry] = []
        for m in data.get("models", []):
            methods = m.get("supportedGenerationMethods", [])
            if "generateContent" not in methods:
                continue
            raw_name: str = m.get("name", "")
            model_id = raw_name.removeprefix("models/")
            entries.append(
                ModelCatalogEntry(
                    id=model_id,
                    name=m.get("displayName", model_id),
                    context_window=m.get("inputTokenLimit"),
                )
            )
        return entries

    # -- Groq ---------------------------------------------------------------

    async def _fetch_groq(
        self,
        client: httpx.AsyncClient,
        api_key: str | None,
    ) -> list[ModelCatalogEntry]:
        """Fetch available Groq models (OpenAI-compatible endpoint)."""
        response = await client.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response.raise_for_status()
        data = response.json()
        return [ModelCatalogEntry(id=m["id"], name=m["id"]) for m in data.get("data", [])]

    # -- OpenRouter ---------------------------------------------------------

    async def _fetch_openrouter(
        self,
        client: httpx.AsyncClient,
        api_key: str | None,
    ) -> list[ModelCatalogEntry]:
        """Fetch available OpenRouter models (capped to keep UI usable)."""
        response = await client.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response.raise_for_status()
        data = response.json()
        return [
            ModelCatalogEntry(
                id=m["id"],
                name=m.get("name", m["id"]),
                context_window=m.get("context_length"),
            )
            for m in data.get("data", [])
        ][: self._openrouter_max_models]

    # -- Z.AI ---------------------------------------------------------------

    async def _fetch_zai(
        self,
        client: httpx.AsyncClient,
        api_key: str | None,
    ) -> list[ModelCatalogEntry]:
        """Fetch available Z.AI models."""
        response = await client.get(
            "https://api.z.ai/api/paas/v4/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response.raise_for_status()
        data = response.json()
        return [
            ModelCatalogEntry(
                id=m["id"],
                name=m.get("id", m["id"]),
            )
            for m in data.get("data", [])
        ]
