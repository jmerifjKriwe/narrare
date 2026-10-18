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

# Intent → governed kb prompt-template mode (route_table.py, kb category).
# Keys MUST be the LLMIntent enum (the service passes enums, not strings)
# and values MUST be the governed template modes ("interview", …) — the
# enum values themselves ("kb_interview", …) are model-routing
# identifiers, not template modes; using them collapses composition into
# PromptNotFoundError (kb/en/kb_interview does not exist). Unmapped
# intents fall back to mode="" so resolve_prompt_route defers to the
# intent's own governed default_mode (single source of truth).
_INTENT_MAP: dict[LLMIntent, str] = {
    LLMIntent.KB_INTERVIEW: "interview",
    LLMIntent.KB_SUGGEST: "suggest",
    LLMIntent.KB_ENHANCE: "enhance",
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
    deps: KBAssistDeps,
    *,
    target_field: str = "",
) -> PromptContext:
    """Build PromptContext for the assist prompt (RULE-02).

    Every feed is derived from the SAME assembled deps the agent
    receives (``build_assist_deps``) so the prompt context can never
    diverge from the agent deps — the F9-2 asymmetry (deps carried
    ``template_structure``/``world_context`` while the prompt context
    fed only ``entity_type``/``existing_answers``) 400'd every
    interview/suggest/enhance compose with MISSING_VARIABLE: the kb
    routes declare no ``optional_variables`` (route_table.py), so each
    of the three templates' placeholders must be fed here:

    - ``{{template_structure}}`` + ``{{world_context}}`` — interview,
      suggest AND enhance.
    - ``{{target_field}}`` / ``{{target_field_description}}`` — suggest
      only (fed from the requested field key + its template label;
      inert extras for the other intents).
    - ``{{user_preferences}}`` / ``{{avoidance_patterns}}`` /
      ``{{writing_language}}`` are PromptContext dataclass fields and
      always render (empty defaults, RULE-11).

    Prompt construction is retained here; composition happens via
    ``compose_invocation`` in ``KBAssistService._run_agent``.
    """
    from narrare_core.prompts.context import PromptContext

    mode = _INTENT_MAP.get(intent, "")
    template_structure = deps.template_structure or {}
    return PromptContext(
        language=deps.language,
        genre=deps.genre,
        project_title="",
        mode=mode,
        extra={
            "entity_type": deps.entity_type,
            "existing_answers": str(deps.existing_answers or {}),
            "template_structure": str(template_structure),
            "world_context": deps.world_context or "",
            "target_field": target_field,
            "target_field_description": template_structure.get(target_field, ""),
        },
    )
