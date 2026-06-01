"""KB Assist Service — orchestrates KBAssistAgent for assisted creation.

Builds agent deps from session state + world context, runs the agent
in the requested mode, and maps output to response schemas. Uses
PromptComposer for system prompts (RULE-02).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.agents.kb_assist_agent import KBAssistAgent, KBAssistDeps
from narrare_core.llm.intents import LLMIntent

from .assist_contracts import (
    KBAssistEnhancementResponse,
    KBAssistQuestionResponse,
    KBAssistSuggestionResponse,
)
from .template_fields import get_template_fields

if TYPE_CHECKING:
    from uuid import UUID

    from pydantic_ai.models import (
        Model,
    )

    from narrare_core.agents.kb_assist_types import KBAssistOutput
    from narrare_core.context.contracts import ProactiveContextProtocol
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)

# Intent mapping for each assist mode.
_INTENT_MAP = {
    "interview": LLMIntent.KB_INTERVIEW,
    "suggest": LLMIntent.KB_SUGGEST,
    "enhance": LLMIntent.KB_ENHANCE,
}


class KBAssistService:
    """Orchestrates KBAssistAgent for assisted creation flows.

    Coordinates:
    - KBAssistAgent (LLM with 4 modes)
    - ProactiveContextService (world context)
    - KB template registry (field structure)
    - PromptComposer (bundled system prompts via RULE-02)

    Uses ModelRegistry + ResolvedModelConfig for lazy model resolution,
    following the new gateway pattern (ADR-015).

    Args:
        registry: ModelRegistry for lazy model resolution.
        config: Resolved model configuration (provider, model, params).
        proactive_context: Service for suggesting relevant KB entries.
        prompt_composer: PromptComposer for bundling system prompts.
        kb_agent: Optional KBAgent for toolset composition.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        config: ResolvedModelConfig,
        proactive_context: ProactiveContextProtocol,
        prompt_composer: PromptComposer,
        kb_agent: object | None = None,
    ) -> None:
        from narrare_core.agents.kb_agent import KBAgent

        self._registry = registry
        self._config = config
        self._proactive_context = proactive_context
        self._prompt_composer = prompt_composer
        self._kb_agent = kb_agent if isinstance(kb_agent, KBAgent) else None

    async def _build_deps(
        self,
        novel_id: UUID,
        entity_type: str,
        existing_fields: dict[str, str],
    ) -> KBAssistDeps:
        """Build KBAssistDeps with world context from ProactiveContextService."""
        # Get template structure for this entity type
        template_fields = get_template_fields(entity_type)
        template_structure = {f.field_key: f.label for f in template_fields}

        # Get proactive context (world context)
        world_context = ""
        try:
            # Note: We need chapter_content for ProactiveContextService.
            # For assisted creation, we use the entity_type + existing values.
            synthetic_content = f"Creating a {entity_type}"
            if existing_fields:
                synthetic_content += ": " + ", ".join(
                    f"{k}={v}" for k, v in existing_fields.items()
                )
            suggestions = await self._proactive_context.suggest(
                synthetic_content,
                novel_id=novel_id,
                entity_names=list(existing_fields.keys()) if existing_fields else [],
                max_results=5,
            )
            if suggestions:
                world_context = "\n".join(
                    f"- {s.name} ({s.entry_type}): relevance {s.relevance_score:.2f}"
                    for s in suggestions
                )
        except Exception:
            logger.warning("proactive_context_unavailable", exc_info=True)

        return KBAssistDeps(
            language="en",
            entity_type=entity_type,
            template_structure=template_structure,
            existing_answers=existing_fields or None,
            world_context=world_context or None,
        )

    async def _build_system_prompt(
        self,
        intent: LLMIntent,
        entity_type: str,
        existing_fields: dict[str, str],
    ) -> str:
        """Build system prompt via PromptComposer (RULE-02)."""
        from narrare_core.prompts.context import PromptContext

        intent_mode = _INTENT_MAP.get(intent, LLMIntent.KB_INTERVIEW)
        ctx = PromptContext(
            language="en",
            genre="",
            project_title="",
            mode=intent_mode.value,
            extra={
                "entity_type": entity_type,
                "existing_answers": str(existing_fields),
            },
        )
        composed = await self._prompt_composer.build(intent, ctx)
        return composed.system

    async def _get_model(self) -> Model:
        """Resolve the LLM model lazily from the registry.

        Uses the injected ``ResolvedModelConfig`` to obtain a configured
        ``Model`` instance.  This allows the service to be instantiated
        before provider credentials are available (e.g. during app startup).
        """
        return await self._registry.get_model(self._config)

    async def _run_agent(
        self,
        user_prompt: str,
        deps: KBAssistDeps,
        system_prompt: str,
    ) -> KBAssistOutput:
        """Run KBAssistAgent with composed system prompt and user prompt."""
        model = await self._get_model()
        agent = KBAssistAgent(
            model=model,
            kb_agent=self._kb_agent,
            system_prompt=system_prompt,
        )
        result = await agent.run(prompt=user_prompt, deps=deps)
        return result

    async def get_interview_question(
        self,
        *,
        novel_id: UUID,
        entity_type: str,
        existing_fields: dict[str, str],
    ) -> KBAssistQuestionResponse:
        """Get next interview question from KBAssistAgent."""
        deps = await self._build_deps(novel_id, entity_type, existing_fields)
        system_prompt = await self._build_system_prompt(
            LLMIntent.KB_INTERVIEW,
            entity_type,
            existing_fields,
        )
        user_prompt = "Ask the next most important question."
        result = await self._run_agent(user_prompt, deps, system_prompt)

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
        deps = await self._build_deps(novel_id, entity_type, existing_fields)
        system_prompt = await self._build_system_prompt(
            LLMIntent.KB_SUGGEST,
            entity_type,
            existing_fields,
        )
        user_prompt = "Suggest a value for the '" + field_key + "' field."
        result = await self._run_agent(user_prompt, deps, system_prompt)

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
        deps = await self._build_deps(novel_id, entity_type, existing_fields)
        system_prompt = await self._build_system_prompt(
            LLMIntent.KB_ENHANCE,
            entity_type,
            existing_fields,
        )
        user_prompt = "Generate a draft entry based on the provided information."
        result = await self._run_agent(user_prompt, deps, system_prompt)

        return KBAssistEnhancementResponse(
            draft_entry=result.draft_entry or {},
            progress=result.progress or 0.5,
            reasoning=result.reasoning,
            context_used=result.context_used or [],
        )
