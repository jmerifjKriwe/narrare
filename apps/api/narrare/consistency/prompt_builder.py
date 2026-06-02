"""Consistency prompt builder — system prompt and user prompt assembly.

Extracted from checker_service.py for RULE-04 compliance (300-line limit).
Contains the inline system prompt (MVP) and the user-facing prompt
construction logic.
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

# ---------------------------------------------------------------------------
# Inline system prompt — MVP approach (Option B from CONS-001 task).
#
# The service attempts PromptComposer first (production path) and falls
# back to this inline prompt if no bundled prompt exists yet.
# Will be migrated to a bundled prompt file once authored.
# ---------------------------------------------------------------------------

CONSISTENCY_SYSTEM_PROMPT = """\
You are a consistency checker for a creative writing project. Your job is to \
detect contradictions and inconsistencies across chapters and entity data.

## Check Types

- **character**: Behavior, voice, knowledge, abilities, physical descriptions.
- **timeline**: Event sequencing, durations, ages, temporal markers.
- **world**: Location properties, system rules, faction relationships, geography.
- **plot**: Cause/effect chains, character motivations, setup/payoff, loose ends.

## Your Task

Compare facts extracted from the chapter prose against the provided KB entity \
data and across chapters. Identify contradictions with severity ratings:

- **error**: Impossible contradiction (e.g., character alive in one chapter, \
dead in next).
- **warning**: Likely inconsistency (e.g., personality trait contradicts behavior).
- **info**: Minor discrepancy (e.g., slight age mismatch that might be \
intentional).

## Output Format

Return a JSON object with:
- `issues`: List of issues found, each with check_type, severity, description, \
  locations, conflicting_facts, suggestion (optional), and confidence (0.0-1.0).
- `overall_assessment`: 1-2 sentence summary of consistency health.
- `checked_types`: Which check types were actually executed.

Be thorough but fair. Not every difference is an inconsistency — allow for \
intentional ambiguity, character development, and unreliable narration.
"""


def get_system_prompt() -> str:
    """Get the consistency check system prompt.

    The Narrare meta-prompt and universal rules are now injected automatically
    by NarrareMeta and NarrareUniversalRules Capabilities (ADR-026).
    No manual meta-prepending needed.
    """
    return CONSISTENCY_SYSTEM_PROMPT


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
