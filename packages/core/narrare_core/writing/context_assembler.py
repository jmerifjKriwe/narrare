"""Writing context assembler — 5-tier context assembly with token budgets.

This module is a pure data transformation.  No I/O, no database, no LLM
calls.  The API layer provides all data; this class organizes it by tier
and enforces token budgets.

Inherits from ``ContextAssembler`` (ADR-025 Decision 3) so all
feature-specific assemblers share the same budget enforcement base.

See CONSTRAINTS.md RULE-02: No prompt building outside ``core/prompts/``.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any

import structlog

from narrare_core.context.assembler import ContextAssembler
from narrare_core.writing._classify import classify_entities
from narrare_core.writing._helpers import extract_frontmatter_references, format_entities
from narrare_core.writing._token_utils import (
    default_token_counter,
    enforce_budget,
    truncate_to_budget,
)
from narrare_core.writing._voice_profiles import extract_voice_profiles
from narrare_core.writing.budget import TokenBudgetManager
from narrare_core.writing.context_validators import check_orphan_references, extract_entity_names
from narrare_core.writing.context_wiki import format_entities_with_wiki
from narrare_core.writing.models import WritingContext

if TYPE_CHECKING:
    from collections.abc import Callable

    from narrare_core.context.types import TierBudget
    from narrare_core.wiki.types import WikiSummaryData
    from narrare_core.writing.context_models import KBEntity, RecentChapter

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Assembler
# ---------------------------------------------------------------------------


class WritingContextAssembler(ContextAssembler[WritingContext]):
    """Assembles writing context from 5 tiers of information.

    This is a pure data transformation — no I/O, no DB, no LLM calls.
    The API layer provides all data; this class organizes it by tier
    and enforces token budgets.

    Inherits from :class:`ContextAssembler` so all feature-specific
    assemblers share the same budget enforcement contract.

    Usage::

        assembler = WritingContextAssembler(total_budget=8000)
        context = await assembler.assemble(
            chapter_content="...",
            kb_entities=[...],
            recent_chapters=[...],
        )
    """

    def __init__(
        self,
        total_budget: int = TokenBudgetManager.DEFAULT_TOTAL_BUDGET,
        token_counter: Callable[[str], int] | None = None,
    ) -> None:
        super().__init__(total_budget)
        self._budget_manager = TokenBudgetManager(total_budget)
        self._count_tokens = token_counter or default_token_counter
        self._truncate = partial(truncate_to_budget, token_counter=self._count_tokens)

    # ------------------------------------------------------------------
    # ContextAssembler contract
    # ------------------------------------------------------------------

    def get_tier_allocation(self, **kwargs: Any) -> dict[str, TierBudget]:
        """Return tier allocation for this assembler's configuration.

        Accepts the same keyword arguments as
        :meth:`TokenBudgetManager.allocate`.
        """
        return self._budget_manager.allocate(**kwargs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def assemble(
        self,
        *,
        chapter_content: str = "",
        chapter_frontmatter: str = "",
        chapter_outline: str = "",
        recent_chapters: list[RecentChapter] | None = None,
        kb_entities: list[KBEntity] | None = None,
        entity_connections: dict[str, set[str]] | None = None,
        wiki_summaries: dict[str, WikiSummaryData] | None = None,
        kb_relationships: str = "",
        project_title: str = "",
        genre: str = "",
        language: str = "en",
        writing_language: str = "",
        tone: str = "balanced",
        word_target: int | None = None,
        user_preferences: str = "",
        avoidance_patterns: str = "",
        mode: str | None = None,
        timeline_position: str = "",
        story_structure: str = "",
        **_extra: Any,
    ) -> WritingContext:
        """Assemble writing context with budget enforcement.

        All data is provided by the caller — no I/O happens here.
        The method is ``async`` to match the protocol but performs
        only synchronous data transformation internally.

        Args:
            wiki_summaries:
                Precomputed wiki summaries keyed by entity ID.  When
                provided, Tier 3 prefers wiki summaries (~40 tokens/entity)
                over raw KB content (~200 tokens/entity) with stale/pending
                fallback.
            kb_relationships:
                Pre-formatted relationship text from the API layer
                (e.g. ``"Aria → [ally of] → Marcus"``).  Passed through
                to :class:`WritingContext` for ``{{kb_relationships}}``
                prompt injection.  FIND-009.
            mode: Generation mode string (e.g. ``"extend"``,
                ``"extend_chapter"``).  When set, adjusts budget
                allocation to prioritise immediate context.
        """
        recent = recent_chapters or []
        entities = kb_entities or []
        is_first = len(recent) == 0
        is_sparse = len(entities) < 3

        budgets = self._budget_manager.allocate(
            first_chapter=is_first,
            mode=mode,
            wiki_optimized=bool(wiki_summaries),
        )
        ref_ids = extract_frontmatter_references(chapter_frontmatter)

        # Classify entities (with optional connection-based promotion)
        connections = entity_connections or {}
        pinned, referenced, connected, suggested = classify_entities(
            entities,
            ref_ids,
            connections,
        )

        # Process tiers with overflow tracking
        overflow = 0

        # Tier 1: Immediate
        t1_limit = budgets["immediate"].token_limit + overflow
        content, overflow = self._apply_tier1(
            chapter_content,
            chapter_frontmatter,
            chapter_outline,
            t1_limit,
        )

        # Tier 2: Recent
        t2_limit = budgets["recent"].token_limit + overflow
        recent_text, overflow = self._apply_tier2(recent, t2_limit)

        # Tier 3: KB Referenced + connected entities (split by entity type)
        t3_limit = budgets["kb_referenced"].token_limit + overflow
        tier3_entities = referenced + connected
        (
            chars_text,
            locs_text,
            factions_text,
            systems_text,
            timelines_text,
            overflow,
            wiki_fresh,
            wiki_stale,
        ) = self._apply_tier3(tier3_entities, t3_limit, wiki_summaries)

        # Tier 4: KB Suggested
        t4_limit = budgets["kb_suggested"].token_limit + overflow
        suggested_raw = format_entities(suggested)
        suggested_text, overflow = enforce_budget(suggested_raw, t4_limit, self._count_tokens)

        # Tier 5: Pinned (bypass — always included)
        pinned_text = format_entities(pinned)

        # Extract character voice profiles from character entities
        character_voice_profiles, voice_profile_warnings = extract_voice_profiles(entities)

        # Check for orphan references (referenced in frontmatter but not in KB)
        all_classified = pinned + referenced + connected + suggested
        orphan_reference_warnings = check_orphan_references(ref_ids, all_classified)

        # Extract entity names for metadata
        char_names, loc_names, fac_names = extract_entity_names(all_classified)

        return WritingContext(
            chapter_content=content,
            chapter_frontmatter=chapter_frontmatter,
            chapter_outline=chapter_outline,
            character_voice_profiles=character_voice_profiles,
            recent_chapters=recent_text,
            recent_chapter_count=len(recent),
            kb_characters=chars_text,
            kb_locations=locs_text,
            kb_factions=factions_text,
            kb_systems=systems_text,
            kb_timelines=timelines_text,
            kb_relationships=kb_relationships,
            kb_suggested=suggested_text,
            kb_pinned=pinned_text,
            project_title=project_title,
            genre=genre,
            language=language,
            writing_language=writing_language,
            tone=tone,
            word_target=word_target,
            story_structure=story_structure,
            timeline_position=timeline_position,
            user_preferences=user_preferences,
            avoidance_patterns=avoidance_patterns,
            is_first_chapter=is_first,
            is_sparse_kb=is_sparse,
            voice_profile_warnings=voice_profile_warnings,
            orphan_reference_warnings=orphan_reference_warnings,
            wiki_summaries_count=wiki_fresh,
            wiki_summaries_stale=wiki_stale,
            character_names=char_names,
            location_names=loc_names,
            faction_names=fac_names,
            total_budget_tokens=self._total_budget,
        )

    # ------------------------------------------------------------------
    # Tier processors
    # ------------------------------------------------------------------

    def _apply_tier1(
        self, content: str, frontmatter: str, outline: str, limit: int
    ) -> tuple[str, int]:
        """Apply tier 1 budget.  Returns (content, overflow).

        Outline and frontmatter are kept intact (typically small).
        Content is truncated only when the combined total exceeds limit.
        """
        fixed_tokens = self._count_tokens(frontmatter) + self._count_tokens(outline)
        content_tokens = self._count_tokens(content)
        total = fixed_tokens + content_tokens

        if total <= limit:
            return content, limit - total

        available = max(0, limit - fixed_tokens)
        truncated = self._truncate(content, available)
        used = fixed_tokens + self._count_tokens(truncated)
        return truncated, max(0, limit - used)

    def _apply_tier2(self, chapters: list[RecentChapter], limit: int) -> tuple[str, int]:
        """Build recent chapters text within budget.

        Prefers full text; falls back to summaries when budget is tight.
        Returns (text, overflow).
        """
        if not chapters:
            return "", limit

        sorted_chapters = sorted(chapters, key=lambda c: c.position, reverse=True)

        # Try full text first
        full_parts = [f"## {ch.title}\n{ch.full_text}" for ch in sorted_chapters]
        full_text = "\n\n".join(full_parts)
        full_tokens = self._count_tokens(full_text)
        if full_tokens <= limit:
            return full_text, limit - full_tokens

        # Fall back to summaries
        summary_parts = [f"## {ch.title}\n{ch.summary}" for ch in sorted_chapters]
        summary_text = "\n\n".join(summary_parts)
        summary_tokens = self._count_tokens(summary_text)
        if summary_tokens <= limit:
            return summary_text, limit - summary_tokens

        # Even summaries too long — truncate
        truncated = self._truncate(summary_text, limit)
        return truncated, 0

    def _apply_tier3(
        self,
        entities: list[KBEntity],
        limit: int,
        wiki_summaries: dict[str, WikiSummaryData] | None = None,
    ) -> tuple[str, str, str, str, str, int, int, int]:
        """Build tier 3 (referenced KB) by entity type.

        Prefers wiki summaries over raw KB content when a fresh wiki
        summary is available (graceful fallback when stale/pending).

        Truncation priority (lowest → highest): systems, factions,
        timelines, locations, characters.

        Returns:
            (characters_text, locations_text, factions_text, systems_text,
             timelines_text, overflow, wiki_fresh_count, wiki_stale_count)
        """
        chars = [e for e in entities if e.entity_type == "character"]
        locs = [e for e in entities if e.entity_type == "location"]
        facs = [e for e in entities if e.entity_type == "faction"]
        systems = [e for e in entities if e.entity_type == "system"]
        timelines = [e for e in entities if e.entity_type == "timeline"]

        chars_text, chars_fresh, chars_stale = format_entities_with_wiki(chars, wiki_summaries)
        locs_text, locs_fresh, locs_stale = format_entities_with_wiki(locs, wiki_summaries)
        facs_text, facs_fresh, facs_stale = format_entities_with_wiki(facs, wiki_summaries)
        systs_text, systs_fresh, systs_stale = format_entities_with_wiki(systems, wiki_summaries)
        times_text, times_fresh, times_stale = format_entities_with_wiki(timelines, wiki_summaries)
        wiki_fresh = chars_fresh + locs_fresh + facs_fresh + systs_fresh + times_fresh
        wiki_stale = chars_stale + locs_stale + facs_stale + systs_stale + times_stale

        chars_tokens = self._count_tokens(chars_text)
        locs_tokens = self._count_tokens(locs_text)
        facs_tokens = self._count_tokens(facs_text)
        systs_tokens = self._count_tokens(systs_text)
        times_tokens = self._count_tokens(times_text)
        total = chars_tokens + locs_tokens + facs_tokens + systs_tokens + times_tokens

        if total <= limit:
            return (
                chars_text,
                locs_text,
                facs_text,
                systs_text,
                times_text,
                limit - total,
                wiki_fresh,
                wiki_stale,
            )

        # Truncation priority (lowest → highest):
        # systems → factions → timelines → locations → characters
        remaining = limit

        # 1. Truncate systems
        after_rest = remaining - chars_tokens - locs_tokens - facs_tokens - times_tokens
        if after_rest < systs_tokens:
            systs_text = self._truncate(systs_text, after_rest) if after_rest > 0 else ""
            systs_tokens = self._count_tokens(systs_text)

        # 2. Truncate factions
        after_chars_locs_times = remaining - chars_tokens - locs_tokens - times_tokens
        if after_chars_locs_times < facs_tokens:
            facs_text = (
                self._truncate(facs_text, after_chars_locs_times)
                if after_chars_locs_times > 0
                else ""
            )
            facs_tokens = self._count_tokens(facs_text)

        # 3. Truncate timelines
        after_chars_locs_facs = remaining - chars_tokens - locs_tokens - facs_tokens
        if after_chars_locs_facs < times_tokens:
            times_text = (
                self._truncate(times_text, after_chars_locs_facs)
                if after_chars_locs_facs > 0
                else ""
            )
            times_tokens = self._count_tokens(times_text)

        # 4. Truncate locations
        after_chars_facs_systs_times = (
            remaining - chars_tokens - facs_tokens - systs_tokens - times_tokens
        )
        if after_chars_facs_systs_times < locs_tokens:
            locs_text = (
                self._truncate(locs_text, after_chars_facs_systs_times)
                if after_chars_facs_systs_times > 0
                else ""
            )
            locs_tokens = self._count_tokens(locs_text)

        # 5. Truncate characters (last resort — highest priority)
        after_locs_facs_systs_times = (
            remaining - locs_tokens - facs_tokens - systs_tokens - times_tokens
        )
        if after_locs_facs_systs_times < chars_tokens:
            chars_text = self._truncate(chars_text, max(0, after_locs_facs_systs_times))

        return chars_text, locs_text, facs_text, systs_text, times_text, 0, wiki_fresh, wiki_stale
