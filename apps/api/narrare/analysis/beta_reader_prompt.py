"""Budget-aware prompt construction for beta reader analysis.

Extracted from ``beta_reader_service.py`` (RULE-04).

The ``BetaReaderDeps`` KB fields carry pre-rendered prompt text produced by
the canonical :class:`~narrare.kb.context_contracts.KBContextProvider`
(decision β — boundary-rendered text). This module only feeds those strings
through :class:`AnalysisContextAssembler` for token-budget enforcement; it
performs no KB fetch or render itself (RULE-02: no prompt building outside
``core/prompts/``; this is runtime data assembly).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare_core.agents.beta_reader_types import BetaReaderDeps
    from narrare_core.analysis.assembler import AnalysisContextAssembler


async def build_budgeted_prompt(
    deps: BetaReaderDeps,
    budget_assembler: AnalysisContextAssembler,
) -> str:
    """Build user prompt with token-budget enforcement.

    Passes the pre-rendered KB-context strings (from the canonical provider,
    ADR-067) and the chapter text through
    :class:`AnalysisContextAssembler` for budget enforcement, then assembles
    the final user prompt from the budget-enforced result.

    Args:
        deps: Fully populated BetaReaderDeps from context assembly. The
            ``kb_characters`` / ``kb_locations`` fields carry rendered envelope
            ``.text`` (empty on empty KB / no provider — RULE-11).
        budget_assembler: Assembler for token-budget enforcement.

    Returns:
        User prompt string with budget-enforced content.
    """
    # Pass the pre-rendered KB strings through the assembler for budget
    # enforcement. The strings already carry provenance (FIND-017) baked in by
    # the provider (annotate_provenance=True).
    budgeted = await budget_assembler.assemble(
        content=deps.chapter_text,
        kb_characters=deps.kb_characters,
        kb_locations=deps.kb_locations,
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
