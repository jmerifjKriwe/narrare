"""Consistency prompt runtime variable formatting.

Extracted from checker_service.py for RULE-04 compliance (300-line limit).
Contains only dynamic data formatting for PromptComposer variables. Prompt
instructions and output-format requirements live in bundled templates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.writing._token_utils import cap_to_budget

if TYPE_CHECKING:
    from narrare_core.agents.consistency_types import (
        ConsistencyCheckType,
        ConsistencyDeps,
    )
    from narrare_core.prompts import PromptComposer

# Maximum KB entries to include in a single check (token budget protection).
MAX_KB_ENTRIES = 100

# Token budget per chapter preview in consistency checks.
# This is a TOKEN limit (not character limit) — ensures language-independent
# context sizing regardless of script density (Latin vs CJK vs Arabic).
MAX_CONSISTENCY_CONTEXT_TOKENS = 2000


def build_consistency_prompt_variables(
    deps: ConsistencyDeps,
    check_types: list[ConsistencyCheckType],
) -> dict[str, str]:
    """Build dynamic variables for the bundled consistency prompt.

    Formats runtime data only. Task instructions, role descriptions, and
    output-format requirements are resolved through PromptComposer templates.

    Args:
        deps: Assembled ConsistencyDeps with chapter texts and KB data.
        check_types: Which check types to run.

    Returns:
        PromptComposer variables for chapter text, KB entities, and check types.
    """
    return {
        "chapter_texts": _format_chapter_texts(deps),
        "kb_entities": _format_kb_entities(deps),
        "check_types": ", ".join(t.value for t in check_types),
    }


async def compose_consistency_prompt(
    composer: PromptComposer,
    language: str,
    deps: ConsistencyDeps,
    check_types: list[ConsistencyCheckType],
) -> tuple[str, str]:
    """Compose the governed consistency prompt with runtime variables.

    Args:
        composer: Injected PromptComposer for cascade resolution.
        language: Output language for prompt resolution.
        deps: Dynamic consistency-analysis data.
        check_types: Check types requested by the caller.

    Returns:
        Tuple of ``(system_prompt, user_prompt)`` from PromptComposer.
    """
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts.context import PromptContext

    variables = build_consistency_prompt_variables(deps, check_types)
    variables["timeline_position"] = ""
    ctx = PromptContext(
        language=language,
        mode="consistency",
        project_title="",
        extra=variables,
    )
    composed = await composer.build(LLMIntent.CONSISTENCY, ctx)
    return composed.system, composed.user


def _format_chapter_texts(deps: ConsistencyDeps) -> str:
    """Format chapter content as dynamic prompt data."""
    parts: list[str] = []

    for ch_id, text in deps.chapter_texts.items():
        # Truncate individual chapters to token budget (not character limit).
        preview = cap_to_budget(text, MAX_CONSISTENCY_CONTEXT_TOKENS)
        parts.append(f"### Chapter {ch_id}\n{preview}\n")
    return "\n".join(parts).strip()


def _format_kb_entities(deps: ConsistencyDeps) -> str:
    """Format KB entity summaries as dynamic prompt data."""
    parts: list[str] = []
    for entity in deps.kb_entity_summaries:
        etype = entity.get("entity_type", "unknown")
        name = entity.get("name", "unnamed")
        fields = entity.get("fields", {})
        parts.append(f"- [{etype}] {name}: {fields}")
    return "\n".join(parts)
