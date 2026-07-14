"""Tier-3 processor for writing context assembly — KB entity budget enforcement.

Handles the most complex tier: splitting KB entities by type and enforcing
a prioritised truncation cascade (other → systems → factions → timelines →
locations → characters) when the combined total exceeds the budget.

Entity types not in :data:`ENTITY_TYPE_TO_BUCKET` are routed to an ``other``
catch-all bucket (CR-AUFG-04-04) instead of being silently dropped, so new
or unrecognised entity types remain visible to the LLM.

Extracted from ``context_assembler.py`` for RULE-04 modularisation.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

import structlog

from narrare_core.context.contracts import RenderedKBContext
from narrare_core.writing._token_utils import truncate_to_budget
from narrare_core.writing.context_wiki import format_entities_with_wiki

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from narrare_core.context._render_options import RenderOptions
    from narrare_core.wiki.types import WikiSummaryData
    from narrare_core.writing.context_models import KBEntity

logger = structlog.get_logger(__name__)

# Entity-type → bucket mapping. Types not listed here are routed to the
# ``other`` catch-all bucket so new/unrecognised entity types are surfaced
# to the LLM (and logged) instead of being silently dropped (CR-AUFG-04-04).
ENTITY_TYPE_TO_BUCKET: Mapping[str, str] = MappingProxyType(
    {
        "character": "characters",
        "location": "locations",
        "faction": "factions",
        "system": "systems",
        "timeline": "timelines",
    }
)
KNOWN_BUCKETS: frozenset[str] = frozenset(ENTITY_TYPE_TO_BUCKET.values())


@dataclass(frozen=True, slots=True)
class Tier3RenderedContext:
    """Rendered Tier-3 context grouped by entity type.

    ``other`` is the catch-all bucket for entity types not in
    :data:`ENTITY_TYPE_TO_BUCKET` (CR-AUFG-04-04).
    """

    characters: RenderedKBContext
    locations: RenderedKBContext
    factions: RenderedKBContext
    systems: RenderedKBContext
    timelines: RenderedKBContext
    other: RenderedKBContext
    overflow: int
    wiki_fresh_count: int
    wiki_stale_count: int


def apply_tier3(
    entities: list[KBEntity],
    limit: int,
    count_tokens: Callable[[str], int],
    wiki_summaries: dict[str, WikiSummaryData] | None = None,
    *,
    options: RenderOptions | None = None,
) -> tuple[str, str, str, str, str, str, int, int, int]:
    """Build tier 3 (referenced KB) by entity type.

    Prefers wiki summaries over raw KB content when a fresh wiki
    summary is available (graceful fallback when stale/pending).

    Entity types outside the known set (character/location/faction/system/
    timeline) are routed to the ``other`` catch-all bucket instead of being
    silently dropped (CR-AUFG-04-04).

    Truncation priority (lowest → highest): other, systems, factions,
    timelines, locations, characters.

    Args:
        entities: Classified KB entities (referenced + connected).
        limit: Token budget for this tier.
        count_tokens: Token counting function.
        wiki_summaries: Precomputed wiki summaries keyed by entity ID.
        options: Per-invocation render controls forwarded to
            :func:`format_entities_with_wiki`. ``None`` (default) is
            byte-for-byte identical to the pre-annotation behaviour.

    Returns:
        (characters_text, locations_text, factions_text, systems_text,
         timelines_text, other_text, overflow, wiki_fresh_count,
         wiki_stale_count)
    """

    rendered = apply_tier3_rendered(entities, limit, count_tokens, wiki_summaries, options=options)
    return (
        rendered.characters.text,
        rendered.locations.text,
        rendered.factions.text,
        rendered.systems.text,
        rendered.timelines.text,
        rendered.other.text,
        rendered.overflow,
        rendered.wiki_fresh_count,
        rendered.wiki_stale_count,
    )


def apply_tier3_rendered(
    entities: list[KBEntity],
    limit: int,
    count_tokens: Callable[[str], int],
    wiki_summaries: dict[str, WikiSummaryData] | None = None,
    *,
    options: RenderOptions | None = None,
) -> Tier3RenderedContext:
    """Build tier 3 as RenderedKBContext objects by entity type."""

    def _truncate(text: str, budget: int) -> str:
        return truncate_to_budget(text, budget, token_counter=count_tokens)

    # Classify entities into known buckets + an ``other`` catch-all.
    # Unknown entity types are surfaced (and logged) instead of dropped.
    buckets: dict[str, list[KBEntity]] = {b: [] for b in KNOWN_BUCKETS}
    other_entities: list[KBEntity] = []
    unclassified_counts: dict[str, int] = {}
    for e in entities:
        bucket = ENTITY_TYPE_TO_BUCKET.get(e.entity_type)
        if bucket is None:
            other_entities.append(e)
            unclassified_counts[e.entity_type] = unclassified_counts.get(e.entity_type, 0) + 1
        else:
            buckets[bucket].append(e)

    for etype, count in unclassified_counts.items():
        logger.warning("tier3_unclassified_entity_type", entity_type=etype, count=count)

    chars = buckets["characters"]
    locs = buckets["locations"]
    facs = buckets["factions"]
    systems = buckets["systems"]
    timelines = buckets["timelines"]

    chars_rendered, chars_fresh, chars_stale = format_entities_with_wiki(
        chars, wiki_summaries, options=options
    )
    locs_rendered, locs_fresh, locs_stale = format_entities_with_wiki(
        locs, wiki_summaries, options=options
    )
    facs_rendered, facs_fresh, facs_stale = format_entities_with_wiki(
        facs, wiki_summaries, options=options
    )
    systs_rendered, systs_fresh, systs_stale = format_entities_with_wiki(
        systems, wiki_summaries, options=options
    )
    times_rendered, times_fresh, times_stale = format_entities_with_wiki(
        timelines, wiki_summaries, options=options
    )
    other_rendered, other_fresh, other_stale = format_entities_with_wiki(
        other_entities, wiki_summaries, options=options
    )
    chars_text = chars_rendered.text
    locs_text = locs_rendered.text
    facs_text = facs_rendered.text
    systs_text = systs_rendered.text
    times_text = times_rendered.text
    other_text = other_rendered.text
    wiki_fresh = chars_fresh + locs_fresh + facs_fresh + systs_fresh + times_fresh + other_fresh
    wiki_stale = chars_stale + locs_stale + facs_stale + systs_stale + times_stale + other_stale

    chars_tokens = count_tokens(chars_text)
    locs_tokens = count_tokens(locs_text)
    facs_tokens = count_tokens(facs_text)
    systs_tokens = count_tokens(systs_text)
    times_tokens = count_tokens(times_text)
    other_tokens = count_tokens(other_text)
    total = chars_tokens + locs_tokens + facs_tokens + systs_tokens + times_tokens + other_tokens

    if total <= limit:
        return Tier3RenderedContext(
            characters=chars_rendered,
            locations=locs_rendered,
            factions=facs_rendered,
            systems=systs_rendered,
            timelines=times_rendered,
            other=other_rendered,
            overflow=limit - total,
            wiki_fresh_count=wiki_fresh,
            wiki_stale_count=wiki_stale,
        )

    # Truncation priority (lowest → highest):
    # other → systems → factions → timelines → locations → characters
    remaining = limit

    # 0. Truncate other (LOWEST priority — unclassified entity types).
    #    Known buckets win budget over unknown ones, so ``other`` is cut first.
    after_named = remaining - chars_tokens - locs_tokens - facs_tokens - systs_tokens - times_tokens
    if after_named < other_tokens:
        other_text = _truncate(other_text, after_named) if after_named > 0 else ""
        other_tokens = count_tokens(other_text)

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

    return Tier3RenderedContext(
        characters=RenderedKBContext(
            text=chars_text,
            preserved_fields=chars_rendered.preserved_fields,
            omitted_fields=chars_rendered.omitted_fields,
            entry_count=chars_rendered.entry_count,
            render_path=chars_rendered.render_path,
        ),
        locations=RenderedKBContext(
            text=locs_text,
            preserved_fields=locs_rendered.preserved_fields,
            omitted_fields=locs_rendered.omitted_fields,
            entry_count=locs_rendered.entry_count,
            render_path=locs_rendered.render_path,
        ),
        factions=RenderedKBContext(
            text=facs_text,
            preserved_fields=facs_rendered.preserved_fields,
            omitted_fields=facs_rendered.omitted_fields,
            entry_count=facs_rendered.entry_count,
            render_path=facs_rendered.render_path,
        ),
        systems=RenderedKBContext(
            text=systs_text,
            preserved_fields=systs_rendered.preserved_fields,
            omitted_fields=systs_rendered.omitted_fields,
            entry_count=systs_rendered.entry_count,
            render_path=systs_rendered.render_path,
        ),
        timelines=RenderedKBContext(
            text=times_text,
            preserved_fields=times_rendered.preserved_fields,
            omitted_fields=times_rendered.omitted_fields,
            entry_count=times_rendered.entry_count,
            render_path=times_rendered.render_path,
        ),
        other=RenderedKBContext(
            text=other_text,
            preserved_fields=other_rendered.preserved_fields,
            omitted_fields=other_rendered.omitted_fields,
            entry_count=other_rendered.entry_count,
            render_path=other_rendered.render_path,
        ),
        overflow=0,
        wiki_fresh_count=wiki_fresh,
        wiki_stale_count=wiki_stale,
    )
