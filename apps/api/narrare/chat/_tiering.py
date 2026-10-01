"""Dynamic tier escalation wiring (ADR-089 pilot) — RULE-04 extraction.

Owns the two backend seams of the opt-in dynamic tier routing pilot, so
``chat_service.py`` and ``_agent_stream.py`` stay within their file-size
limits and single responsibilities (RULE-04/RULE-06):

- :func:`resolve_tier_escalation` — consumed by
  ``ChatService.ensure_resolved`` at first use (ADR-086 lazy seam). The
  escalation cascade's ``ConfigurationError`` degrades to base-only with
  one loud warning (ADR-089 Decision 5, RULE-11) — chat never hard-fails
  on the opt-in path.
- :func:`build_tier_capabilities` — flag-gated ``SelectModel`` capability
  build: the escalation ``Model`` is constructed through
  ``ModelRegistry.get_model`` (RULE-01b — the gateway stays the only model
  factory) with the escalation credentials, wrapped with the base model
  via the Core module's ``build_tiered_model`` under the live
  ``CoreSettings`` policy knobs, with provider attribution logged at
  attach time (D7 — the core selector logs ``Model.model_name`` only).

Default-off (ADR-089 Decision 2): flag off → ``chat/dependencies.py``
passes no escalation resolution → nothing here ever runs.

See: docs/architecture/decisions/ADR-089-dynamic-tier-routing-selectmodel.md
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from narrare_core.settings import get_core_settings

if TYPE_CHECKING:
    from pydantic_ai.models import Model

    from narrare._app.dependencies_services import ModelResolution
    from narrare_core.llm import ModelRegistry, ResolvedModel, ResolvedModelConfig

logger = structlog.get_logger(__name__)

__all__ = ["build_tier_capabilities", "resolve_tier_escalation"]


async def resolve_tier_escalation(resolution: ModelResolution) -> ResolvedModel | None:
    """Resolve the escalation (ANALYSE) cascade; degrade loudly on failure.

    ADR-089 Decision 5: ``ConfigurationError`` — the cascade's documented
    "no provider configured" signal — is the ONLY degraded outcome: one
    structured ``dynamic_tier_degraded`` warning, then ``None`` (always
    base). Any other error propagates (RULE-11: bugs are never swallowed).

    Args:
        resolution: The lazy ANALYSE routing cascade wired by
            ``chat/dependencies.py`` (same resolver instance and user as
            the CHAT cascade, no project tier).

    Returns:
        The resolved escalation triple, or ``None`` when no capable-tier
        provider is configured for the user (degraded mode).
    """
    from narrare_core.shared.errors import ConfigurationError

    try:
        return await resolution.resolve()
    except ConfigurationError as exc:
        logger.warning(
            "dynamic_tier_degraded",
            stage="escalation_resolution",
            error=str(exc),
        )
        return None


async def build_tier_capabilities(
    registry: ModelRegistry,
    base_model: Model,
    base_config: ResolvedModelConfig,
    escalation: ResolvedModel,
) -> list[Any] | None:
    """Build the ``SelectModel`` capability list for tier escalation.

    Flag-gated (ADR-089 Decision 2/7): the pilot flag is re-checked here so
    a flag flip between DI time and stream time degrades to the static
    path. The escalation ``Model`` is built through the gateway with the
    escalation cascade's per-user credentials; runtime ``ModelSettings``
    stay base-composed (Decision 4 — v1 escalates the model instance only).
    ``ConfigurationError`` during the escalation build degrades loudly to
    ``None`` (Decision 5, RULE-11); everything else propagates.

    Args:
        registry: The gateway — sole model factory (RULE-01b).
        base_model: The already-prepared base CHAT model (constructor
            model for the ``ChatAgent`` — kept authoritative per the
            upstream ``model_is_explicit`` invariant).
        base_config: The base CHAT cascade config (attach-time provider
            attribution).
        escalation: The resolved escalation (ANALYSE) triple.

    Returns:
        ``[capability]`` for the ``ChatAgent(capabilities=...)`` keyword,
        or ``None`` (stay base-only) when the flag is off or the capable
        tier cannot be built.
    """
    from narrare_core.llm.dynamic_tiering import TieringPolicy, build_tiered_model
    from narrare_core.shared.errors import ConfigurationError

    settings = get_core_settings()
    if not settings.llm_dynamic_tiering_enabled:
        return None
    try:
        escalation_model = await registry.get_model(
            escalation.config,
            api_key=escalation.api_key,
            base_url=escalation.base_url,
        )
        capability = build_tiered_model(
            base_model,
            escalation_model,
            policy=TieringPolicy(
                max_prompt_chars=settings.llm_dynamic_tiering_max_prompt_chars,
                min_turns=settings.llm_dynamic_tiering_min_turns,
            ),
        )
    except ConfigurationError:
        logger.warning(
            "dynamic_tier_degraded",
            stage="escalation_model_build",
            base_provider=base_config.provider_name,
            base_model=base_config.model_id,
            escalation_provider=escalation.config.provider_name,
            escalation_model=escalation.config.model_id,
        )
        return None
    # D7 obligation: provider attribution from the configs held at attach
    # time — the core selector only logs ``Model.model_name``.
    logger.info(
        "dynamic_tier_attached",
        base_provider=base_config.provider_name,
        base_model=base_config.model_id,
        escalation_provider=escalation.config.provider_name,
        escalation_model=escalation.config.model_id,
    )
    return [capability]
