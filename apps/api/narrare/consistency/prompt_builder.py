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


def build_consistency_prompt_variables(
    deps: ConsistencyDeps,
    check_types: list[ConsistencyCheckType],
    max_chapter_tokens: int = 2000,
) -> dict[str, str]:
    """Build dynamic variables for the bundled consistency prompt.

    Formats runtime data only. Task instructions, role descriptions, and
    output-format requirements are resolved through PromptComposer templates.

    Args:
        deps: Assembled ConsistencyDeps with chapter texts, KB data, and timeline events.
        check_types: Which check types to run.
        max_chapter_tokens: Maximum tokens per chapter preview.

    Returns:
        PromptComposer variables for chapter text, KB entities, timeline, and check types.
    """
    return {
        "chapter_texts": _format_chapter_texts(deps, max_chapter_tokens=max_chapter_tokens),
        "kb_entities": _format_kb_entities(deps),
        "timeline_position": _format_timeline_events(deps),
        "check_types": ", ".join(t.value for t in check_types),
    }


async def compose_consistency_prompt(
    composer: PromptComposer,
    language: str,
    deps: ConsistencyDeps,
    check_types: list[ConsistencyCheckType],
    max_chapter_tokens: int = 2000,
) -> tuple[str, str]:
    """Compose the governed consistency prompt with runtime variables.

    Args:
        composer: Injected PromptComposer for cascade resolution.
        language: Output language for prompt resolution.
        deps: Dynamic consistency-analysis data.
        check_types: Check types requested by the caller.
        max_chapter_tokens: Maximum tokens per chapter preview.

    Returns:
        Tuple of ``(system_prompt, user_prompt)`` from PromptComposer.
    """
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts.context import PromptContext

    variables = build_consistency_prompt_variables(
        deps,
        check_types,
        max_chapter_tokens=max_chapter_tokens,
    )
    ctx = PromptContext(
        language=language,
        mode="consistency",
        project_title="",
        extra=variables,
    )
    composed = await composer.build(LLMIntent.CONSISTENCY, ctx)
    return composed.system, composed.user


def _format_chapter_texts(
    deps: ConsistencyDeps,
    max_chapter_tokens: int = 2000,
) -> str:
    """Format chapter content as dynamic prompt data."""
    parts: list[str] = []

    for ch_id, text in deps.chapter_texts.items():
        # Truncate individual chapters to token budget (not character limit).
        preview = cap_to_budget(text, max_chapter_tokens)
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


def _format_timeline_events(deps: ConsistencyDeps) -> str:
    """Format timeline events as dynamic prompt data for temporal consistency.

    Each event dict contains: event_name, timestamp, character, location.
    Produces a compact timeline summary the LLM can use to detect temporal
    contradictions (e.g., a character in two places at once).

    Returns:
        Formatted timeline string, or empty string when no events are provided
        (backward-compatible with checks that don't include timeline data).
    """
    if not deps.timeline_events:
        return ""

    parts: list[str] = ["## Timeline Events"]
    for event in deps.timeline_events:
        name = event.get("event_name", "Unnamed event")
        timestamp = event.get("timestamp", "")
        character = event.get("character", "")
        location = event.get("location", "")

        # Format: - [timestamp] "event_name" — character; location
        ts_label = f"[{timestamp}]" if timestamp else "[?]"
        detail_parts: list[str] = []
        if character:
            detail_parts.append(character)
        if location:
            detail_parts.append(location)
        detail = "; ".join(detail_parts)

        if detail:
            parts.append(f'- {ts_label} "{name}" — {detail}')
        else:
            parts.append(f'- {ts_label} "{name}"')

    return "\n".join(parts)
