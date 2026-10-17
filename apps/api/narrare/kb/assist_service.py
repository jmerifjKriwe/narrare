"""KB Assist Service — orchestrates KBAssistAgent for assisted creation.

Builds agent deps from session state + world context, runs the agent
in the requested mode, and maps output to response schemas. Uses
PromptComposer for system prompts (RULE-02).

The per-user model routing cascade is wired as a ``LazyModelResolution``
and resolves on first use (ADR-086) — never at construction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from narrare_core.agents.kb_assist_agent import KBAssistAgent, KBAssistDeps
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.shared.errors import (
    ConfigurationError,
    InvocationValidationError,
    PromptError,
)

from ._assist_context import build_assist_deps, build_prompt_context
from .assist_contracts import (
    KBAssistEnhancementResponse,
    KBAssistQuestionResponse,
    KBAssistSuggestionResponse,
)

if TYPE_CHECKING:
    from uuid import UUID

    from narrare._app.dependencies_services import ModelResolution
    from narrare.kb.context_contracts import KBContextProviderProtocol
    from narrare_core.agents.kb_assist_types import KBAssistOutput
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm._prepared_call import PreparedModelCall
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.model_routing import ResolvedModel
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


class KBAssistService:
    """Orchestrates KBAssistAgent for assisted creation flows.

    Coordinates:
    - KBAssistAgent (LLM with 4 modes)
    - KBContextProvider (canonical world context, ADR-067)
    - KB template registry (field structure)
    - PromptComposer (bundled system prompts via RULE-02)

    Uses ModelRegistry + the ADR-086 lazy ``ModelResolution`` seam for
    model access, following the new gateway pattern (ADR-015).

    Args:
        registry: ModelRegistry for lazy model resolution.
        model_resolution: Lazy per-user model resolution (ADR-086) — the
            routing cascade resolves on first use, never at construction.
        kb_context_provider: Single source for curated world context
            (ADR-067). Renders existing KB entries of the entity type as
            ``- name (type): brief`` and degrades to empty (RULE-11).
        prompt_composer: PromptComposer for bundling system prompts.
        kb_agent: Optional KBAgent for toolset composition.
        invocation_pipeline: Optional invocation evidence pipeline (ADR-040).
    """

    def __init__(
        self,
        registry: ModelRegistry,
        model_resolution: ModelResolution,
        kb_context_provider: KBContextProviderProtocol,
        prompt_composer: PromptComposer,
        kb_agent: object | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
    ) -> None:
        from narrare_core.agents.kb_agent import KBAgent

        self._registry = registry
        self._model_resolution = model_resolution
        self._resolved: ResolvedModel | None = None
        self._kb_context_provider = kb_context_provider
        self._prompt_composer = prompt_composer
        self._kb_agent = kb_agent if isinstance(kb_agent, KBAgent) else None
        self._invocation_pipeline = invocation_pipeline
        self._run_limit_resolver = run_limit_resolver or DefaultRunLimitResolver()

    async def ensure_resolved(self) -> ResolvedModel:
        """Resolve the per-user model routing once; idempotent (ADR-086).

        First call resolves via the injected ``ModelResolution`` and
        caches the triple; repeat calls return the cached value without
        re-running the cascade. Errors propagate loudly and are never
        cached (RULE-11): ``ConfigurationError`` (``NO_AI_PROVIDER``)
        surfaces as a 400 on this AI-mandatory endpoint.
        """
        if self._resolved is None:
            self._resolved = await self._model_resolution.resolve()
        return self._resolved

    async def _prepare(self, intent: LLMIntent) -> PreparedModelCall:
        """Resolve the coherent call triple lazily from the registry.

        Single assembly point (Task 6c — Task 4/5 pattern): model +
        intent-aware runtime settings + usage limits as one result. The
        intent is dynamic — each public assist method passes its own
        (KB_INTERVIEW / KB_SUGGEST / KB_ENHANCE). Per-user credentials
        come from the (cached) ADR-086 first-use routing resolution so
        the user's wizard-configured provider is used, not the operator
        env.
        """
        resolved = await self.ensure_resolved()
        limits = self._run_limit_resolver.resolve(
            config=resolved.config, budget=None, invocation_id=uuid4()
        )
        return await self._registry.prepare(
            resolved.config,
            intent=intent,
            usage_limits=limits.usage_limits,
            api_key=resolved.api_key,
            base_url=resolved.base_url,
        )

    async def _run_agent(
        self,
        user_prompt: str,
        deps: KBAssistDeps,
        intent: LLMIntent,
        target_field: str = "",
    ) -> KBAssistOutput:
        """Run KBAssistAgent with composer-driven system prompt (Mode 1).

        Composes the invocation via the pipeline (ADR-048 Mode 1) so
        enrichment flows through the composer into the system prompt.
        The prompt context is built from the SAME ``deps`` the agent
        receives (single source — the F9-2 fix); ``target_field`` feeds
        the suggest template's target-field slots (inert elsewhere).
        """
        from narrare._app.invocation_context import build_invocation_context
        from narrare_core.ai_invocation import compose_invocation

        prompt_context = build_prompt_context(intent, deps, target_field=target_field)
        invocation_context = build_invocation_context(
            feature_id="kb_assist",
            intent=intent,
        )
        try:
            invocation_result = await compose_invocation(
                invocation_pipeline=self._invocation_pipeline,
                invocation_context=invocation_context,
                composer=self._prompt_composer,
                prompt_context=prompt_context,
                intent=intent,
            )
            # Mode 1 invariant (ADR-048): composed_prompt is non-None.
            # Guard replaces a prior runtime `assert` (RULE-11: typed error).
            composed_prompt = invocation_result.composed_prompt
            if composed_prompt is None:  # pragma: no cover
                raise ConfigurationError(
                    "Prompt composition produced no system prompt for KB assist.",
                    code="COMPOSITION_EMPTY",
                )
            system_prompt = composed_prompt.system
        except (InvocationValidationError, PromptError, ConfigurationError) as exc:
            # Graceful degradation: named composition-failure modes fall back.
            logger.warning(
                "invocation_composition_degraded",
                feature_id="kb_assist",
                error_code=getattr(exc, "code", type(exc).__name__),
                exc_info=True,
            )
            composed = await self._prompt_composer.build(intent, prompt_context)
            system_prompt = composed.system

        prepared = await self._prepare(intent)
        agent = KBAssistAgent(
            model=prepared.model,
            kb_agent=self._kb_agent,
            system_prompt=system_prompt,
        )
        result = await agent.run(
            prompt=user_prompt,
            deps=deps,
            model_settings=prepared.model_settings,
            usage_limits=prepared.usage_limits,
        )
        return result

    async def get_interview_question(
        self,
        *,
        novel_id: UUID,
        entity_type: str,
        existing_fields: dict[str, str],
    ) -> KBAssistQuestionResponse:
        """Get next interview question from KBAssistAgent."""
        deps = await build_assist_deps(
            self._kb_context_provider, novel_id, entity_type, existing_fields
        )
        user_prompt = "Ask the next most important question."
        result = await self._run_agent(
            user_prompt=user_prompt,
            deps=deps,
            intent=LLMIntent.KB_INTERVIEW,
        )

        return KBAssistQuestionResponse(
            field_key=result.field_key or "general",
            question=result.question or "",
            reasoning=result.reasoning,
        )

    async def get_suggestion(
        self,
        *,
        novel_id: UUID,
        entity_type: str,
        field_key: str,
        existing_fields: dict[str, str],
    ) -> KBAssistSuggestionResponse:
        """Get AI suggestion for a specific field."""
        deps = await build_assist_deps(
            self._kb_context_provider, novel_id, entity_type, existing_fields
        )
        user_prompt = "Suggest a value for the '" + field_key + "' field."
        result = await self._run_agent(
            user_prompt=user_prompt,
            deps=deps,
            intent=LLMIntent.KB_SUGGEST,
            target_field=field_key,
        )

        return KBAssistSuggestionResponse(
            field_key=result.field_key or field_key,
            suggestion=result.suggestion or "",
            reasoning=result.reasoning,
            context_used=result.context_used or [],
        )

    async def get_enhancement(
        self,
        *,
        novel_id: UUID,
        entity_type: str,
        existing_fields: dict[str, str],
    ) -> KBAssistEnhancementResponse:
        """Get AI-enhanced draft of multiple fields."""
        deps = await build_assist_deps(
            self._kb_context_provider, novel_id, entity_type, existing_fields
        )
        user_prompt = "Generate a draft entry based on the provided information."
        result = await self._run_agent(
            user_prompt=user_prompt,
            deps=deps,
            intent=LLMIntent.KB_ENHANCE,
        )

        return KBAssistEnhancementResponse(
            draft_entry=result.draft_entry or {},
            progress=result.progress or 0.5,
            reasoning=result.reasoning,
            context_used=result.context_used or [],
        )
