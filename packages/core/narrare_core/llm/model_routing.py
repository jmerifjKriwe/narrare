"""
Model routing resolver — Protocol and result types.

Defines the ``ModelRoutingResolver`` protocol that the backend service
layer implements to resolve which model to use for a given intent.

The cascade priority is:
    project_intent → project_category → user_intent → user_category → user_default
    → ConfigurationError

This module lives in core/ because it defines the *contract* — the
backend (apps/) provides the implementation that reads from DB/Redis.

See: openspec/changes/configurable-model-routing/design.md (D3, D7, D8)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.intents import LLMIntent


@dataclass(frozen=True, slots=True)
class ResolvedModel:
    """Result of model routing resolution.

    Bundles the resolved model config with credentials and cascade
    metadata for observability.

    Attributes:
        config: Fully resolved model configuration.
        api_key: Provider API key (decrypted, never logged).
            ``None`` means the provider reads from env vars (dev/test).
        base_url: Custom base URL for OpenAI-compatible providers.
            ``None`` means use the provider's default endpoint.
        source: Which cascade level resolved this model, e.g.
            ``"project_intent"``, ``"user_category"``, ``"user_default"``.
            Used for logging and debugging.
    """

    config: ResolvedModelConfig
    api_key: str | None = None
    base_url: str | None = None
    source: str = ""


@runtime_checkable
class ModelRoutingResolver(Protocol):
    """Protocol for resolving which model to use for an LLM call.

    The backend implements this by checking the configuration cascade:
    project override → user override → user default → error.

    The gateway never calls this directly — the *service layer* calls
    the resolver and passes the result to the gateway.

    Example implementation flow::

        from narrare_core.agents.summary_agent import ChapterSummaryAgent, SummaryDeps

        model = await registry.get_model(config)
        agent = ChapterSummaryAgent(model=model)
        deps = SummaryDeps(language="en", genre="Fantasy", chapter_title="Chapter 1")
        result = await agent.run(prompt="Content...", deps=deps)
        print(result.summary)
    """

    def resolve(
        self,
        intent: LLMIntent,
        user_id: UUID,
        project_id: UUID | None,
    ) -> ResolvedModel:
        """Resolve model configuration for a given intent and context.

        Args:
            intent: The LLM operation intent.
            user_id: User whose settings to check.
            project_id: Optional project for project-level overrides.

        Returns:
            ``ResolvedModel`` with config, credentials, and source metadata.

        Raises:
            ConfigurationError: If no provider is configured for this user.
        """
        ...
