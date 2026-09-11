"""PreparedWikiAgent — binds the ModelRegistry.prepare() triple halves.

API-layer adapter (Task 2 of the pydantic-ai follow-ups plan): the core
``WikiService`` drives its agent through ``WikiAgentProtocol``, whose
methods carry no ``model_settings``/``usage_limits`` parameters, while
the wiki factory resolves the full prepared triple via the single
assembly point (``ModelRegistry.prepare``). This adapter binds the
settings/limits halves at construction and forwards them into every
concrete ``WikiGenerationAgent`` call, so the intent-aware settings and
the usage limits reach the pydantic-ai runs.

Alternative rejected: extending ``WikiAgentProtocol`` +
``WikiService`` in packages/core to thread the kwargs — Core-scope
change (layer boundary), while the triple is resolved API-side here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.usage import UsageLimits

    from narrare_core.wiki.agent import WikiGenerationAgent
    from narrare_core.wiki.types import (
        WikiChapterOutput,
        WikiEntityOutput,
        WikiGenerationDeps,
    )


class PreparedWikiAgent:
    """Binding adapter: concrete wiki agent + prepared settings/limits.

    Implements the core ``WikiAgentProtocol`` surface structurally, so
    the core ``WikiService`` uses it transparently (RULE-12 — no core
    change). Every ``generate_entity``/``generate_chapter`` call
    forwards the bound halves into the concrete agent's kwargs
    pass-through (core Task 1).
    """

    def __init__(
        self,
        agent: WikiGenerationAgent,
        *,
        model_settings: ModelSettings | None,
        usage_limits: UsageLimits | None,
    ) -> None:
        """Bind the prepared halves to the concrete agent.

        Args:
            agent: Concrete ``WikiGenerationAgent`` (model-injected).
            model_settings: Settings half of the ``ModelRegistry.prepare()``
                triple — forwarded on every generation call.
            usage_limits: Usage limits from the prepared triple —
                forwarded on every generation call.
        """
        self._agent = agent
        self._model_settings = model_settings
        self._usage_limits = usage_limits

    async def generate_entity(
        self,
        deps: WikiGenerationDeps,
        *,
        stream: bool = False,
    ) -> WikiEntityOutput:
        """Generate an entity summary with the bound prepared halves."""
        return await self._agent.generate_entity(
            deps,
            stream=stream,
            model_settings=self._model_settings,
            usage_limits=self._usage_limits,
        )

    async def generate_chapter(
        self,
        deps: WikiGenerationDeps,
        *,
        stream: bool = False,
    ) -> WikiChapterOutput:
        """Generate a chapter summary with the bound prepared halves."""
        return await self._agent.generate_chapter(
            deps,
            stream=stream,
            model_settings=self._model_settings,
            usage_limits=self._usage_limits,
        )
