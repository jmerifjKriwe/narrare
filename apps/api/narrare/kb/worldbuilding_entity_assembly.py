"""Worldbuilding entity assembly — data collection and prioritization helpers.

Extracted from ``worldbuilding_analyzer.py`` for RULE-04 compliance.
Handles entity listing, summary building, token-budget prioritization,
and template/relationship-type lookup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare_core.agents.worldbuilding_types import Phase1EntitySummary, WorldbuildingDeps
from narrare_core.kb.relationships import suggested_for
from narrare_core.kb.schemas.registry import get_schema

if TYPE_CHECKING:
    from narrare.kb.contracts import KBRepositoryProtocol, RelationshipRepositoryProtocol
    from narrare.kb.models import KBEntry

logger = structlog.get_logger(__name__)


async def build_deps(
    kb_repo: KBRepositoryProtocol,
    rel_repo: RelationshipRepositoryProtocol,
    novel_id: UUID,
    entity_types: list[str] | None,
) -> tuple[WorldbuildingDeps, int]:
    """Assemble entity data into WorldbuildingDeps.

    Moved from ``worldbuilding_analyzer._build_deps`` (RULE-04): this module
    owns entity assembly; the analyzer orchestrates phases.
    """
    entities = await list_entities(kb_repo, novel_id, entity_types)
    total_count = len(entities)
    if not entities:
        return WorldbuildingDeps(language="en"), 0

    adjacency = await get_adjacency_safe(rel_repo, novel_id, entities)
    summaries = build_entity_summaries(entities, adjacency)
    prioritized = prioritize_entities(summaries)
    relationships = await get_relationships_for(prioritized, rel_repo)

    type_set = {e.entity_type for e in entities}
    return WorldbuildingDeps(
        language="en",
        entity_summaries=prioritized,
        template_structures=build_template_structures(type_set),
        existing_relationships=relationships,
        available_rel_types=build_available_rel_types(type_set),
    ), total_count


async def list_entities(
    kb_repo: KBRepositoryProtocol,
    novel_id: UUID,
    entity_types: list[str] | None,
) -> list[KBEntry]:
    """Paginate through all entities, optionally filtered by types."""
    entries: list[KBEntry] = []
    page = 1
    while True:
        batch, _ = await kb_repo.list_entries(
            novel_id=novel_id,
            page=page,
            page_size=100,
        )
        entries.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    if entity_types:
        valid = set(entity_types)
        return [e for e in entries if e.entity_type in valid]
    return entries


async def get_adjacency_safe(
    rel_repo: RelationshipRepositoryProtocol,
    novel_id: UUID,
    entities: list[KBEntry],
) -> dict[str, set[str]]:
    """Get adjacency map, returning empty dict on failure."""
    try:
        return await rel_repo.get_adjacency_map(novel_id, {e.id for e in entities})
    except Exception:
        logger.warning("adjacency_map_unavailable", exc_info=True)
        return {}


def build_entity_summaries(
    entities: list[KBEntry],
    adjacency: dict[str, set[str]],
) -> list[Phase1EntitySummary]:
    """Build Phase1EntitySummary for each entity."""
    summaries: list[Phase1EntitySummary] = []
    for entity in entities:
        eid = str(entity.id)
        metadata = dict(entity.metadata_ or {})
        field_keys = list(get_schema(entity.entity_type).model_fields.keys())
        summaries.append(
            Phase1EntitySummary(
                entry_id=eid,
                name=entity.name,
                entity_type=entity.entity_type,
                field_fill_rate=_compute_fill_rate(metadata, field_keys),
                relationship_count=len(adjacency.get(eid, set())),
                has_body=bool(entity.body and entity.body.strip()),
                chapter_references=entity.usage_count,
            )
        )
    return summaries


def prioritize_entities(
    summaries: list[Phase1EntitySummary],
    budget: int = 8000,
) -> list[Phase1EntitySummary]:
    """Apply 4-tier entity prioritization within token budget.

    Priority 1: chapter_references > 0 (~500 tokens each, max 10).
    Priority 2: relationship_count >= 3 (~200 tokens each, max 10).
    Priority 3: remaining (~50 tokens each, max 20).
    Priority 4: isolated with no references — omitted if over budget.
    """
    ranked = sorted(
        summaries,
        key=lambda s: (-s.chapter_references, -s.relationship_count, s.name),
    )
    result: list[Phase1EntitySummary] = []
    used = 0
    included: set[str] = set()

    # Tier 1: chapter-referenced
    for s in ranked:
        if s.chapter_references > 0 and len(result) < 10 and used + 500 <= budget:
            result.append(s)
            included.add(s.entry_id)
            used += 500

    # Tier 2: well-connected
    t2 = 0
    for s in ranked:
        if (
            s.entry_id not in included
            and s.relationship_count >= 3
            and t2 < 10
            and used + 200 <= budget
        ):
            result.append(s)
            included.add(s.entry_id)
            t2 += 1
            used += 200

    # Tier 3: remaining
    t3 = 0
    for s in ranked:
        if s.entry_id not in included and t3 < 20 and used + 50 <= budget:
            result.append(s)
            included.add(s.entry_id)
            t3 += 1
            used += 50

    return result


async def get_relationships_for(
    summaries: list[Phase1EntitySummary],
    rel_repo: RelationshipRepositoryProtocol,
) -> list[dict[str, object]]:
    """Fetch relationships for given entities, deduplicated by ID."""
    seen: set[str] = set()
    rels: list[dict[str, object]] = []
    for s in summaries:
        for r in await rel_repo.list_for_entry(UUID(s.entry_id)):
            rid = str(r.id)
            if rid not in seen:
                seen.add(rid)
                rels.append(
                    {
                        "id": rid,
                        "source_id": str(r.source_id),
                        "target_id": str(r.target_id),
                        "rel_type": r.rel_type,
                        "direction": r.direction,
                    }
                )
    return rels


def build_template_structures(entity_types: set[str]) -> dict[str, dict[str, object]]:
    """Build template field definitions keyed by entity type."""
    return {
        etype: {
            name: (info.description or name.replace("_", " ").title())
            for name, info in get_schema(etype).model_fields.items()
        }
        for etype in entity_types
    }


def build_available_rel_types(entity_types: set[str]) -> dict[str, list[str]]:
    """Build entity-type-pair -> possible relationship types mapping."""
    result: dict[str, list[str]] = {}
    for src in sorted(entity_types):
        for tgt in sorted(entity_types):
            suggestions = suggested_for(src, tgt)
            if suggestions:
                result[f"{src}->{tgt}"] = suggestions
    return result


def _compute_fill_rate(metadata: dict[str, object], field_keys: list[str]) -> float:
    """Compute fraction of template fields that are non-empty."""
    if not field_keys:
        return 1.0
    filled = sum(1 for f in field_keys if metadata.get(f) not in (None, "", [], {}))
    return filled / len(field_keys)
