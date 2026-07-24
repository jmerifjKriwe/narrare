"""
Anthropic provider adapter.

Registered as: "anthropic"
Models: claude-* family
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from anthropic import AsyncAnthropic
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from narrare_core.llm._providers.registry import register, register_model
from narrare_core.llm._transport_retry import get_transport_max_retries
from narrare_core.settings import get_core_settings

if TYPE_CHECKING:
    from pydantic_ai.models import Model


def _make_anthropic(
    model_id: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Model:
    """Create an Anthropic model.

    Transport retry (transient 429/5xx/timeout) is governed at the provider
    layer via :func:`get_transport_max_retries` (ADR-060) and applied to the
    SDK client's ``max_retries`` — uniformly for ``run()`` and ``stream()``.

    Credential resolution (so retry applies on every call-bearing path,
    including the local-first operator-env path):

    * ``api_key`` arg (per-user credential from the DB) takes precedence;
    * otherwise the ``ANTHROPIC_API_KEY`` environment variable is resolved.

    When a credential is resolvable, an explicit ``AsyncAnthropic`` client is
    constructed so the governed ``max_retries`` takes effect. When no
    credential is resolvable, construction is deferred to pydantic-ai.

    Args:
        model_id: Anthropic model identifier (e.g. "claude-sonnet-4-5-20251020").
        api_key: Optional API key — overrides env var when provided.
        base_url: Optional base URL — for proxy endpoints.

    Returns:
        Configured AnthropicModel instance.
    """
    max_retries = get_transport_max_retries()
    resolved_key = api_key if api_key is not None else get_core_settings().anthropic_api_key
    if resolved_key is not None:
        client = AsyncAnthropic(api_key=resolved_key, base_url=base_url, max_retries=max_retries)
        return AnthropicModel(model_id, provider=AnthropicProvider(anthropic_client=client))
    if base_url is not None:
        return AnthropicModel(model_id, provider=AnthropicProvider(api_key=None, base_url=base_url))
    return AnthropicModel(model_id)


register("anthropic", _make_anthropic)

# Register known Claude model IDs explicitly — avoids prefix-based inference
for _mid in [
    "claude-sonnet-4-5-20251020",
    "claude-haiku-3-5-20241022",
    "claude-opus-4-20250514",
]:
    register_model(_mid, "anthropic")
