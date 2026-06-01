"""Budget-aware prompt construction for beta reader analysis.

Extracted from beta_reader_service.py (RULE-04).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare_core.agents.beta_reader_types import BetaReaderDeps
    from narrare_core.analysis.assembler import AnalysisContextAssembler


def format_kb_items(items: list[dict[str, str]]) -> str:
    """Format a list of KB entry dicts into a single string.

    Args:
        items: KB entries with ``name`` and ``summary`` keys.

    Returns:
        Formatted string like ``"- Alice: A warrior\\n- Bob: A mage"``.
    """
    return "\n".join(f"- {item['name']}: {item.get('summary', '')}" for item in items)


async def build_budgeted_prompt(
    deps: BetaReaderDeps,
    budget_assembler: AnalysisContextAssembler,
) -> str:
    """Build user prompt with token-budget enforcement.

    Formats BetaReaderDeps data into strings, passes them through
    :class:`AnalysisContextAssembler` for budget enforcement, then
    assembles the final user prompt from the budget-enforced result.

    Args:
        deps: Fully populated BetaReaderDeps from context assembly.
        budget_assembler: Assembler for token-budget enforcement.

    Returns:
        User prompt string with budget-enforced content.
    """
    # Format KB data into strings for budget enforcement
    kb_chars = format_kb_items(deps.kb_characters)
    kb_locs = format_kb_items(deps.kb_locations)

    # Pass through assembler for budget enforcement
    budgeted = await budget_assembler.assemble(
        content=deps.chapter_text,
        kb_characters=kb_chars,
        kb_locations=kb_locs,
    )

    # Build prompt from budget-enforced strings
    parts: list[str] = []

    if deps.genre:
        parts.append(f"Genre: {deps.genre}")

    parts.append(f"Chapters: {', '.join(deps.chapter_titles)}")
    parts.append(f"Word count: {deps.word_count}")

    if deps.focus_categories:
        parts.append(f"Focus categories: {', '.join(deps.focus_categories)}")

    if deps.previous_chapter_summaries:
        parts.append("\n## Previous Chapter Summaries")
        for i, summary in enumerate(deps.previous_chapter_summaries, 1):
            parts.append(f"Chapter {i}: {summary}")

    if budgeted.get("kb_characters"):
        parts.append("\n## Characters")
        parts.append(budgeted["kb_characters"])

    if budgeted.get("kb_locations"):
        parts.append("\n## Locations")
        parts.append(budgeted["kb_locations"])

    parts.append("\n## Chapter Text")
    parts.append(budgeted["content"])

    parts.append("\nAnalyze this chapter as a beta reader.")

    return "\n".join(parts)
