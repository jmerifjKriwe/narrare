"""Core wiki service factory — shared by the user-facing and operator planes.

Model planes (Task 6 user-routing migration):
- User plane: ``get_wiki_service`` (``dependencies.py``) passes a resolved
  config + credentials; they are threaded into the actual ``get_model``
  call so the provider authenticates as the user.
- Operator plane (``config=None``): builds the system-default WRITING
  config. Reserved for the STARTUP wiki listener in ``_app/lifespan.py``
  — no user context exists at lifespan startup. Plan-sanctioned survivor
  (user-routing migration plan, Global Constraints).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.wiki.contracts import WikiServiceProtocol


async def build_core_wiki_service(
    invocation_pipeline: InvocationPipeline | None = None,
    *,
    config: ResolvedModelConfig | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> WikiServiceProtocol:
    """Create the core WikiService with agent, event bus, and optional pipeline.

    Two planes:
    - ``config=None`` (operator plane): builds the system-default WRITING
      config. Reserved for the STARTUP wiki listener (``_app/lifespan.py``)
      — no user context exists at lifespan startup.
    - ``config`` given (user plane): uses the per-user resolved config and
      threads api_key/base_url into the actual ``get_model`` call.

    Args:
        invocation_pipeline: Optional InvocationPipeline for evidence
            recording (ADR-048). When ``None``, pipeline is skipped.
        config: Resolved model config from the per-user routing cascade
            (user plane), or ``None`` for the operator plane.
        api_key: Per-user provider API key (user plane).
        base_url: Optional per-user provider base URL override (user plane).

    Returns:
        A configured WikiService instance.
    """
    from narrare._app.dependencies import get_model_registry
    from narrare._app.dependencies_services import (
        SystemModelCategory,
        build_system_default_config,
    )
    from narrare_core.events.bus import NullEventBus
    from narrare_core.wiki.agent import WikiGenerationAgent
    from narrare_core.wiki.service import WikiService

    registry = get_model_registry()
    if config is None:
        # Operator plane — startup wiki listener only (plan-sanctioned
        # survivor): no user context exists at lifespan startup.
        config = build_system_default_config(
            SystemModelCategory.WRITING, temperature=0.7, max_tokens=4096
        )
        model = await registry.get_model(config)
    else:
        model = await registry.get_model(config, api_key=api_key, base_url=base_url)
    agent = WikiGenerationAgent(model=model)
    return WikiService(
        agent=agent,
        event_bus=NullEventBus(),
        invocation_pipeline=invocation_pipeline,
    )
