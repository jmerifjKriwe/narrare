"""
Z.AI provider adapter.

Registered as: "zai"
Models: glm-* family via Z.AI OpenAI-compatible endpoints

Z.AI exposes two endpoints:
- General API: https://api.z.ai/api/paas/v4
- Coding API:  https://api.z.ai/api/coding/paas/v4

See: docs/agents/architecture/questions/Q-005-resolved.md
ADR: ADR-006 (tech stack)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles import merge_profile
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.zai import ZaiProvider

from narrare_core.llm._providers.registry import register, register_model
from narrare_core.llm._schema_transformer import narrare_openai_compat_profile
from narrare_core.llm._transport_retry import get_transport_max_retries
from narrare_core.settings import get_core_settings

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.profiles import ModelProfile

_ZAI_GENERAL_URL = "https://api.z.ai/api/paas/v4"
_ZAI_CODING_URL = "https://api.z.ai/api/coding/paas/v4"

_ZAI_MODEL_PROFILE: ModelProfile = OpenAIModelProfile(
    openai_chat_supports_max_completion_tokens=False,
    supports_thinking=True,
)
"""Narrare-declared Z.AI capability fragment (on top of ``ZaiProvider``).

By default ``OpenAIChatModel`` maps the ``max_tokens`` model setting to
``max_completion_tokens``; Z.AI silently ignores that field, which would drop
runtime output caps (ADR-045) and let generation run unbounded. Upstream's
``ZaiProvider.model_profile`` does **not** set this flag (verified against
pydantic-ai 2.31.0), so Narrare declares the delta here.

``supports_thinking=True`` declares the GLM thinking capability: pydantic-ai
only resolves the unified ``ModelSettings['thinking']`` setting (mapped to
``reasoning_content`` on the wire via the provider's own
``openai_chat_thinking_field`` fact) when the model profile declares thinking
support. Upstream marks only ``glm-5``/``glm-4.7``/``glm-4.6``/``glm-4.5``
IDs as thinking-capable; Narrare's registered IDs (``glm-z1-32b``, ``glm-4-*``,
``chatglm-4``) would silently lose the runtime thinking default injected by
:func:`narrare_core.llm._model_settings.build_runtime_model_settings`.
"""


def _zai_profile(resolved: ModelProfile) -> ModelProfile:
    """Resolved-profile hook applied to every Z.AI model (``profile=`` callable).

    Composes the universal OpenAI-compat schema inlining
    (:func:`narrare_openai_compat_profile` — ``$ref``/``$defs`` inlined because
    Z.AI does not resolve JSON Schema references natively, unlike OpenAI proper)
    with the Z.AI capability fragment (:data:`_ZAI_MODEL_PROFILE`). The callable
    receives the fully provider-resolved profile, so all DEFAULT/provider keys
    are retained.
    """
    return merge_profile(narrare_openai_compat_profile(resolved), _ZAI_MODEL_PROFILE)


def _make_zai(
    model_id: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Model:
    """Create a Z.AI model using the General API endpoint.

    When ``api_key`` is provided, uses it directly. Otherwise falls back
    to the ``ZAI_API_KEY`` environment variable.

    Transport retry (transient 429/5xx/timeout) is governed at the provider
    layer via :func:`get_transport_max_retries` (ADR-060) and applied to the
    SDK client's ``max_retries`` — uniformly for ``run()`` and ``stream()``.

    The model is built through pydantic-ai's native ``ZaiProvider`` (which
    imports upstream capability facts: ``reasoning_content`` thinking field,
    thinking-part send-back, JSON-object output) with a Narrare-declared
    transport-retry client (``openai_client=``), so ADR-060 survives.

    The model profile (``_zai_profile``) composes the universal OpenAI-compat
    ``$ref``/``$defs`` inlining transformer, ``openai_chat_supports_max_completion_tokens=False``
    so output caps reach Z.AI as ``max_tokens``, and ``supports_thinking=True``
    so the runtime thinking default resolves.

    Args:
        model_id: Z.AI model identifier (e.g. "glm-z1-32b").
        api_key: Optional API key — overrides env var when provided.
        base_url: Optional base URL — defaults to Z.AI General API.

    Returns:
        Configured OpenAIChatModel via Z.AI endpoint.
    """
    max_retries = get_transport_max_retries()
    resolved_key = api_key or (get_core_settings().zai_api_key or "")
    resolved_base = base_url or _ZAI_GENERAL_URL
    if resolved_key:
        client = AsyncOpenAI(api_key=resolved_key, base_url=resolved_base, max_retries=max_retries)
        return OpenAIChatModel(
            model_id, provider=ZaiProvider(openai_client=client), profile=_zai_profile
        )
    # No resolvable key: ``ZaiProvider()`` validates credential availability
    # eagerly (reads ``ZAI_API_KEY`` itself) and raises ``UserError`` if
    # nothing resolves — preserving the fail-fast behaviour.
    return OpenAIChatModel(model_id, provider=ZaiProvider(), profile=_zai_profile)


def make_zai_coding(
    model_id: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Model:
    """Create a Z.AI model using the Coding API endpoint.

    Used for code-generation intents. Not registered by default —
    call explicitly when needed.

    Transport retry is governed identically to the General endpoint
    (:func:`get_transport_max_retries`, ADR-060). The model profile is shared
    with ``_make_zai`` (see :func:`_zai_profile`).

    Args:
        model_id: Z.AI model identifier.
        api_key: Optional API key — overrides env var when provided.
        base_url: Optional base URL — defaults to Z.AI Coding API.

    Returns:
        Configured OpenAIChatModel via Z.AI Coding endpoint.
    """
    max_retries = get_transport_max_retries()
    resolved_key = api_key or (get_core_settings().zai_api_key or "")
    resolved_base = base_url or _ZAI_CODING_URL
    if resolved_key:
        client = AsyncOpenAI(api_key=resolved_key, base_url=resolved_base, max_retries=max_retries)
        return OpenAIChatModel(
            model_id, provider=ZaiProvider(openai_client=client), profile=_zai_profile
        )
    return OpenAIChatModel(model_id, provider=ZaiProvider(), profile=_zai_profile)


register("zai", _make_zai)

# Register known Z.AI model IDs explicitly — avoids prefix-based inference
for _mid in [
    "glm-z1-32b",
    "glm-4-flash",
    "glm-4-plus",
    "chatglm-4",
]:
    register_model(_mid, "zai")
