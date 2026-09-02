"""KB assist context helpers — agent-deps and prompt-context assembly.

Extracted from ``assist_service.py`` for RULE-04 compliance (hard
300-line service limit). Owns the KBAssistDeps assembly (template
structure + curated world context, ADR-067) and the PromptContext
assembly (RULE-02) used by the assist agent flows; the LLM
orchestration stays in the service.

See:
    :class:`narrare.kb.assist_service.KBAssistService`
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.agents.kb_assist_agent import KBAssistDeps
from narrare_core.llm.intents import LLMIntent

from .template_fields import get_template_fields

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.context_contracts import KBContextProviderProtocol
    from narrare_core.prompts.context import PromptContext

# Intent mapping for each assist mode.
_INTENT_MAP = {
    "interview": LLMIntent.KB_INTERVIEW,
    "suggest": LLMIntent.KB_SUGGEST,
    "enhance": LLMIntent.KB_ENHANCE,
}


async def build_assist_deps(
    kb_context_provider: KBContextProviderProtocol,
    novel_id: UUID,
    entity_type: str,
    existing_fields: dict[str, str],
) -> KBAssistDeps:
    """Build KBAssistDeps with world context from the KBContextProvider.

    World context is the canonical curated KB aggregate (ADR-067):
    existing entries of the entity type, rendered as
    ``- name (type): brief``. Degrades to empty on an unavailable
    repository or empty KB (RULE-11, handled inside the provider) so
    assist always composes its deps.
    """
    # Get template structure for this entity type
    template_fields = get_template_fields(entity_type)
    template_structure = {f.field_key: f.label for f in template_fields}

    # Single source for KB world context (ADR-067). The provider owns
    # RULE-11 degradation (empty string on missing/empty KB).
    world_context = await kb_context_provider.fetch_world_context(
        novel_id,
        entity_type=entity_type,
    )

    return KBAssistDeps(
        language="en",
        entity_type=entity_type,
        template_structure=template_structure,
        existing_answers=existing_fields or None,
        world_context=world_context or None,
    )


def build_prompt_context(
    intent: LLMIntent,
    entity_type: str,
    existing_fields: dict[str, str],
) -> PromptContext:
    """Build PromptContext for the assist prompt (RULE-02).

    Prompt construction is retained here; composition happens via
    ``compose_invocation`` in ``KBAssistService._run_agent``.
    """
    from narrare_core.prompts.context import PromptContext

    intent_mode = _INTENT_MAP.get(intent, LLMIntent.KB_INTERVIEW)
    return PromptContext(
        language="en",
        genre="",
        project_title="",
        mode=intent_mode.value,
        extra={
            "entity_type": entity_type,
            "existing_answers": str(existing_fields),
        },
    )
