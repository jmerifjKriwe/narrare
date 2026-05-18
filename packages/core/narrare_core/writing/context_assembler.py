"""Writing context assembler — 5-tier context assembly with token budgets.

This module is a pure data transformation.  No I/O, no database, no LLM
calls.  The API layer provides all data; this class organizes it by tier
and enforces token budgets.

See CONSTRAINTS.md RULE-02: No prompt building outside ``core/prompts/``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.shared.frontmatter import parse_frontmatter
from narrare_core.writing.budget import TokenBudgetManager
from narrare_core.writing.models import WritingContext

if TYPE_CHECKING:
    from collections.abc import Callable

    from narrare_core.writing.context_models import KBEntity, RecentChapter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REFERENCE_KEYS: frozenset[str] = frozenset(
    {
        "pov_character",
        "characters",
        "location",
        "locations",
        "faction",
        "factions",
    }
)


def _default_token_counter(text: str) -> int:
    """Approximate token count: words x 1.3.

    Avoids a tiktoken dependency in core.  The API layer can inject a
    more accurate counter via the constructor.
    """
    if not text:
        return 0
    return round(len(text.split()) * 1.3)


# ---------------------------------------------------------------------------
# Assembler
# ---------------------------------------------------------------------------


class WritingContextAssembler:
    """Assembles writing context from 5 tiers of information.

    This is a pure data transformation — no I/O, no DB, no LLM calls.
    The API layer provides all data; this class organizes it by tier
    and enforces token budgets.

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
        self._budget_manager = TokenBudgetManager(total_budget)
        self._count_tokens = token_counter or _default_token_counter

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
        project_title: str = "",
        genre: str = "",
        language: str = "en",
        tone: str = "balanced",
        word_target: int | None = None,
        user_preferences: str = "",
        avoidance_patterns: str = "",
    ) -> WritingContext:
        """Assemble writing context with budget enforcement.

        All data is provided by the caller — no I/O happens here.
        The method is ``async`` to match the protocol but performs
        only synchronous data transformation internally.
        """
        recent = recent_chapters or []
        entities = kb_entities or []
        is_first = len(recent) == 0
        is_sparse = len(entities) < 3

        budgets = self._budget_manager.allocate(first_chapter=is_first)
        ref_ids = self._extract_frontmatter_references(chapter_frontmatter)

        # Classify entities
        pinned = [e for e in entities if e.is_pinned]
        referenced = [
            e for e in entities if not e.is_pinned and (e.entity_id in ref_ids or e.is_referenced)
        ]
        suggested = sorted(
            [
                e
                for e in entities
                if not e.is_pinned and e.entity_id not in ref_ids and not e.is_referenced
            ],
            key=lambda e: e.relevance_score,
            reverse=True,
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

        # Tier 3: KB Referenced (split by entity type)
        t3_limit = budgets["kb_referenced"].token_limit + overflow
        chars_text, locs_text, factions_text, overflow = self._apply_tier3(
            referenced,
            t3_limit,
        )

        # Tier 4: KB Suggested
        t4_limit = budgets["kb_suggested"].token_limit + overflow
        suggested_raw = self._format_entities(suggested)
        suggested_text, overflow = self._enforce_budget(suggested_raw, t4_limit)

        # Tier 5: Pinned (bypass — always included)
        pinned_text = self._format_entities(pinned)

        return WritingContext(
            chapter_content=content,
            chapter_frontmatter=chapter_frontmatter,
            chapter_outline=chapter_outline,
            recent_chapters=recent_text,
            recent_chapter_count=len(recent),
            kb_characters=chars_text,
            kb_locations=locs_text,
            kb_factions=factions_text,
            kb_suggested=suggested_text,
            kb_pinned=pinned_text,
            project_title=project_title,
            genre=genre,
            language=language,
            tone=tone,
            word_target=word_target,
            user_preferences=user_preferences,
            avoidance_patterns=avoidance_patterns,
            is_first_chapter=is_first,
            is_sparse_kb=is_sparse,
        )

    # ------------------------------------------------------------------
    # Tier processors
    # ------------------------------------------------------------------

    def _apply_tier1(
        self,
        content: str,
        frontmatter: str,
        outline: str,
        limit: int,
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
        truncated = self._truncate_to_budget(content, available)
        used = fixed_tokens + self._count_tokens(truncated)
        return truncated, max(0, limit - used)

    def _apply_tier2(
        self,
        chapters: list[RecentChapter],
        limit: int,
    ) -> tuple[str, int]:
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
        truncated = self._truncate_to_budget(summary_text, limit)
        return truncated, 0

    def _apply_tier3(
        self,
        entities: list[KBEntity],
        limit: int,
    ) -> tuple[str, str, str, int]:
        """Build tier 3 (referenced KB) by entity type.

        Priority order for truncation: factions > locations > characters.
        Returns (characters_text, locations_text, factions_text, overflow).
        """
        chars = [e for e in entities if e.entity_type == "character"]
        locs = [e for e in entities if e.entity_type == "location"]
        facs = [e for e in entities if e.entity_type == "faction"]

        chars_text = self._format_entities(chars)
        locs_text = self._format_entities(locs)
        facs_text = self._format_entities(facs)

        chars_tokens = self._count_tokens(chars_text)
        locs_tokens = self._count_tokens(locs_text)
        facs_tokens = self._count_tokens(facs_text)
        total = chars_tokens + locs_tokens + facs_tokens

        if total <= limit:
            return chars_text, locs_text, facs_text, limit - total

        # Truncate by priority: factions first, then locations, then characters
        remaining = limit

        # 1. Truncate factions
        after_chars_locs = remaining - chars_tokens - locs_tokens
        if after_chars_locs < facs_tokens:
            facs_text = (
                self._truncate_to_budget(facs_text, after_chars_locs)
                if after_chars_locs > 0
                else ""
            )
            facs_tokens = self._count_tokens(facs_text)

        # 2. Truncate locations
        after_chars_facs = remaining - chars_tokens - facs_tokens
        if after_chars_facs < locs_tokens:
            locs_text = (
                self._truncate_to_budget(locs_text, after_chars_facs)
                if after_chars_facs > 0
                else ""
            )
            locs_tokens = self._count_tokens(locs_text)

        # 3. Truncate characters (last resort)
        after_locs_facs = remaining - locs_tokens - facs_tokens
        if after_locs_facs < chars_tokens:
            chars_text = self._truncate_to_budget(
                chars_text,
                max(0, after_locs_facs),
            )

        return chars_text, locs_text, facs_text, 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_frontmatter_references(self, frontmatter: str) -> set[str]:
        """Extract entity IDs referenced in chapter frontmatter.

        Looks for keys: ``pov_character``, ``characters``, ``location``,
        ``locations``, ``faction``, ``factions``.  Returns a set of entity
        ID strings.  Returns an empty set for empty or unparsable input.
        """
        if not frontmatter.strip():
            return set()

        parsed = parse_frontmatter(frontmatter)
        if not parsed.has_frontmatter:
            return set()

        ids: set[str] = set()
        for key in _REFERENCE_KEYS:
            value = parsed.metadata.get(key)
            if value is None:
                continue
            if isinstance(value, list):
                for item in value:  # pyright: ignore[reportUnknownVariableType]
                    if item is not None:
                        ids.add(str(item))  # pyright: ignore[reportUnknownArgumentType]
            else:
                ids.add(str(value))  # pyright: ignore[reportUnknownArgumentType]
        return ids

    def _format_entities(self, entities: list[KBEntity]) -> str:
        """Format entities as a readable text block."""
        if not entities:
            return ""
        parts: list[str] = []
        for entity in entities:
            header = f"### {entity.entity_type.title()}: {entity.name}"
            parts.append(f"{header}\n{entity.content}")
        return "\n\n".join(parts)

    def _truncate_to_budget(self, text: str, token_limit: int) -> str:
        """Truncate text to fit within token budget.

        Uses word-level truncation.  Returns empty string when
        ``token_limit <= 0``.
        """
        if not text or token_limit <= 0:
            return ""
        current = self._count_tokens(text)
        if current <= token_limit:
            return text
        max_words = int(token_limit / 1.3)
        words = text.split()
        return " ".join(words[:max_words])

    def _enforce_budget(self, text: str, limit: int) -> tuple[str, int]:
        """Enforce token budget on text.  Returns (text, overflow)."""
        tokens = self._count_tokens(text)
        if tokens <= limit:
            return text, limit - tokens
        return self._truncate_to_budget(text, limit), 0
