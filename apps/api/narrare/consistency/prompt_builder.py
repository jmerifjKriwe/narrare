"""Consistency prompt builder — system prompt and user prompt assembly.

Extracted from checker_service.py for RULE-04 compliance (300-line limit).
Contains the user-facing prompt construction logic. The system prompt is
resolved through PromptComposer and bundled prompt templates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.writing._token_utils import cap_to_budget

if TYPE_CHECKING:
    from narrare_core.agents.consistency_types import (
        ConsistencyCheckType,
        ConsistencyDeps,
    )

# Maximum KB entries to include in a single check (token budget protection).
MAX_KB_ENTRIES = 100

# Token budget per chapter preview in consistency checks.
# This is a TOKEN limit (not character limit) — ensures language-independent
# context sizing regardless of script density (Latin vs CJK vs Arabic).
MAX_CONSISTENCY_CONTEXT_TOKENS = 2000


def build_user_prompt(
    deps: ConsistencyDeps,
    check_types: list[ConsistencyCheckType],
) -> str:
    """Build the user-facing analysis request prompt for the agent.

    Concatenates chapter content and KB entity context into a clear,
    structured request the agent can analyze.

    Args:
        deps: Assembled ConsistencyDeps with chapter texts and KB data.
        check_types: Which check types to run.

    Returns:
        Formatted prompt string for the ConsistencyAgent.
    """
    parts: list[str] = []

    parts.append("Check the following content for consistency issues.\n")

    # Chapter content
    ch_count = len(deps.chapter_texts)
    parts.append(f"## Chapters ({ch_count} total)\n")
    for ch_id, text in deps.chapter_texts.items():
        # Truncate individual chapters to token budget (not character limit).
        preview = cap_to_budget(text, MAX_CONSISTENCY_CONTEXT_TOKENS)
        parts.append(f"### Chapter {ch_id}\n{preview}\n")

    # KB entity context
    if deps.kb_entity_summaries:
        parts.append(
            f"\n## KB Entities ({len(deps.kb_entity_summaries)} total)\n",
        )
        for entity in deps.kb_entity_summaries:
            etype = entity.get("entity_type", "unknown")
            name = entity.get("name", "unnamed")
            fields = entity.get("fields", {})
            parts.append(f"- [{etype}] {name}: {fields}")

    # Check types
    type_names = [t.value for t in check_types]
    parts.append(f"\n## Check types to run: {', '.join(type_names)}")

    parts.append(
        "\nAnalyze the chapters for consistency issues. "
        "Compare facts across chapters and against KB entity data. "
        "Return structured findings with severity ratings.",
    )

    return "\n".join(parts)
