"""Tier-3 processor for writing context assembly — KB entity budget enforcement.

Handles the most complex tier: splitting KB entities by type and enforcing
a prioritised truncation cascade (systems → factions → timelines →
locations → characters) when the combined total exceeds the budget.

Extracted from ``context_assembler.py`` for RULE-04 modularisation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.writing._token_utils import truncate_to_budget
from narrare_core.writing.context_wiki import format_entities_with_wiki

if TYPE_CHECKING:
    from collections.abc import Callable

    from narrare_core.wiki.types import WikiSummaryData
    from narrare_core.writing.context_models import KBEntity


def apply_tier3(
    entities: list[KBEntity],
    limit: int,
    count_tokens: Callable[[str], int],
    wiki_summaries: dict[str, WikiSummaryData] | None = None,
) -> tuple[str, str, str, str, str, int, int, int]:
    """Build tier 3 (referenced KB) by entity type.

    Prefers wiki summaries over raw KB content when a fresh wiki
    summary is available (graceful fallback when stale/pending).

    Truncation priority (lowest → highest): systems, factions,
    timelines, locations, characters.

    Args:
        entities: Classified KB entities (referenced + connected).
        limit: Token budget for this tier.
        count_tokens: Token counting function.
        wiki_summaries: Precomputed wiki summaries keyed by entity ID.

    Returns:
        (characters_text, locations_text, factions_text, systems_text,
         timelines_text, overflow, wiki_fresh_count, wiki_stale_count)
    """

    def _truncate(text: str, budget: int) -> str:
        return truncate_to_budget(text, budget, token_counter=count_tokens)

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

    chars_tokens = count_tokens(chars_text)
    locs_tokens = count_tokens(locs_text)
    facs_tokens = count_tokens(facs_text)
    systs_tokens = count_tokens(systs_text)
    times_tokens = count_tokens(times_text)
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
        systs_text = _truncate(systs_text, after_rest) if after_rest > 0 else ""
        systs_tokens = count_tokens(systs_text)

    # 2. Truncate factions
    after_chars_locs_times = remaining - chars_tokens - locs_tokens - times_tokens
    if after_chars_locs_times < facs_tokens:
        facs_text = (
            _truncate(facs_text, after_chars_locs_times) if after_chars_locs_times > 0 else ""
        )
        facs_tokens = count_tokens(facs_text)

    # 3. Truncate timelines
    after_chars_locs_facs = remaining - chars_tokens - locs_tokens - facs_tokens
    if after_chars_locs_facs < times_tokens:
        times_text = (
            _truncate(times_text, after_chars_locs_facs) if after_chars_locs_facs > 0 else ""
        )
        times_tokens = count_tokens(times_text)

    # 4. Truncate locations
    after_chars_facs_systs_times = (
        remaining - chars_tokens - facs_tokens - systs_tokens - times_tokens
    )
    if after_chars_facs_systs_times < locs_tokens:
        locs_text = (
            _truncate(locs_text, after_chars_facs_systs_times)
            if after_chars_facs_systs_times > 0
            else ""
        )
        locs_tokens = count_tokens(locs_text)

    # 5. Truncate characters (last resort — highest priority)
    after_locs_facs_systs_times = (
        remaining - locs_tokens - facs_tokens - systs_tokens - times_tokens
    )
    if after_locs_facs_systs_times < chars_tokens:
        chars_text = _truncate(chars_text, max(0, after_locs_facs_systs_times))

    return chars_text, locs_text, facs_text, systs_text, times_text, 0, wiki_fresh, wiki_stale
