"""Consistency checker support — prompt resolution (RULE-04 split).

``resolve_system_prompt`` was relocated unchanged from
``ConsistencyCheckerService``: the ADR-086 L13 lazy-resolution seam
(``ensure_resolved`` + the ``ModelResolution`` ctor swap) pushed
``checker_service.py`` past the 300-line service limit (RULE-04), and
this seam — composed when the legacy runner was extracted and left
orphaned on the service — is the module's designated split unit.

Prompt instructions live in bundled templates (RULE-02); this helper
only forwards the cascade build for the CONSISTENCY intent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare_core.prompts import PromptComposer


async def resolve_system_prompt(composer: PromptComposer, language: str) -> str:
    """Resolve the system prompt for the consistency agent.

    Uses the bundled prompt cascade. Locale fallback to English is
    handled by PromptRegistry — no production inline fallback needed.

    Args:
        composer: PromptComposer for system prompt assembly.
        language: Output language for the PromptContext.

    Returns:
        The composed CONSISTENCY system prompt.
    """
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts.context import PromptContext

    ctx = PromptContext(
        language=language,
        mode="consistency",
        project_title="",
    )
    composed = await composer.build(LLMIntent.CONSISTENCY, ctx)
    return composed.system
