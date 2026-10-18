"""Wiki service support helpers — RULE-04 split from ``service.py``.

Ownership gate, generation-deps assembly, generation transaction, and
read-side response builders. Wiki semantics here are deliberate and
pinned:

- Ownership violations raise ``ForbiddenError`` (403) — the KB-plane
  semantics, NOT the canonical ``novels.ownership`` gate (404); that
  module's SSOT note explicitly excludes this family from consolidation.
- ``system_mode`` bypasses the caller check: background tasks are
  system-level operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.wiki.chapter_service import ChapterWikiService
from narrare.wiki.prompt_version import WIKI_PROMPT_VERSION
from narrare.wiki.schemas import WikiIndexResponse, WikiSummaryListResponse, WikiSummaryResponse
from narrare_core.shared.errors import ForbiddenError
from narrare_core.wiki.types import (
    WikiGenerationDeps,
    WikiSummaryData,
    WikiSummaryStatus,
)

if TYPE_CHECKING:
    import uuid

    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.kb.contracts import KBRepositoryProtocol, RelationshipRepositoryProtocol
    from narrare.kb.models import KBEntry
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.novels.models import Novel
    from narrare.wiki.repository import WikiRepository
    from narrare_core.wiki.contracts import WikiServiceProtocol
    from narrare_core.wiki.types import WikiEntityOutput

__all__ = [
    "build_generation_deps",
    "build_summary_data",
    "build_wiki_index",
    "compose_chapter_wiki_service",
    "generate_and_persist_summary",
    "list_summaries",
    "verify_novel_ownership",
]

logger = structlog.get_logger(__name__)


async def verify_novel_ownership(
    novel_repo: NovelRepositoryProtocol,
    novel_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    system_mode: bool = False,
) -> Novel:
    """Return the novel if accessible, else raise ForbiddenError.

    When ``system_mode`` is True, loads the novel without checking
    ownership — background tasks are system-level operations.

    Args:
        novel_repo: Novel repository — the ownership lookup.
        novel_id: The novel being accessed.
        user_id: The caller's identity (skipped in system mode).
        system_mode: Bypass the caller check (system plane).

    Returns:
        The loaded Novel.

    Raises:
        ForbiddenError: The novel is unknown or not accessible by the
            caller (wiki/KB-plane semantics — 403).
    """
    if system_mode:
        novel = await novel_repo.get(novel_id)
    else:
        novel = await novel_repo.get_by_id(novel_id, user_id)
    if novel is None:
        raise ForbiddenError("You do not have access to this novel")
    return novel


async def build_generation_deps(
    relationship_repo: RelationshipRepositoryProtocol,
    entity: KBEntry,
    novel: Novel,
) -> WikiGenerationDeps:
    """Build WikiGenerationDeps from entity + novel + relationships."""
    rels = await relationship_repo.list_for_entry(entity.id)
    return WikiGenerationDeps(
        language=novel.writing_language or "en",
        genre=novel.genre or "",
        entity_type=entity.entity_type,
        entity_name=entity.name,
        entity_body=entity.body or "",
        entity_metadata=dict(entity.metadata_) if entity.metadata_ else {},
        relationships=[
            {
                "entity_id": str(r.target_id if r.source_id == entity.id else r.source_id),
                "rel_type": r.rel_type,
                "label": r.label,
            }
            for r in rels
        ],
        chapter_context=[],
    )


def build_summary_data(
    entity_id: uuid.UUID,
    novel_id: uuid.UUID,
    result: WikiEntityOutput,
) -> WikiSummaryData:
    """Map a core generation result to the persistable summary data.

    ``depends_on`` carries the wiki prompt version — the staleness
    snapshot ``mark_all_stale`` version-gates on. Left empty, the
    summary could never be marked stale (the JSONB filter skips
    NULL/empty ``depends_on`` rows — 2026-10-18 E2E finding).
    """
    return WikiSummaryData(
        entity_id=str(entity_id),
        novel_id=str(novel_id),
        narrative_summary=result.narrative_summary,
        role_in_story=result.role_in_story,
        key_attributes=result.key_attributes,
        relationships=result.relationships,
        character_arc=result.character_arc,
        depends_on={"wiki_prompt_version": WIKI_PROMPT_VERSION},
        status=WikiSummaryStatus.FRESH,
    )


async def generate_and_persist_summary(
    wiki_repo: WikiRepository,
    kb_repo: KBRepositoryProtocol,
    novel_repo: NovelRepositoryProtocol,
    relationship_repo: RelationshipRepositoryProtocol,
    core: WikiServiceProtocol,
    entity_id: uuid.UUID,
    novel_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    system_mode: bool = False,
) -> WikiSummaryResponse | None:
    """Generation transaction: verify → load → generate → persist.

    The core service must already be composed — the ADR-086 first-use
    seam happens at the service boundary, ahead of these gates.
    Outside this function's graceful degradation: ``ConfigurationError``
    (unconfigured provider) propagates un-swallowed (loud RULE-11 —
    wiki is an AI-mandatory feature).
    """
    try:
        novel = await verify_novel_ownership(
            novel_repo,
            novel_id,
            user_id,
            system_mode=system_mode,
        )
        entity = await kb_repo.get_by_id(entity_id)
        if entity is None or entity.novel_id != novel_id:
            logger.warning("wiki_entity_not_found", entity_id=str(entity_id))
            return None

        deps = await build_generation_deps(relationship_repo, entity, novel)
        result = await core.generate_entity_summary(
            entity_id=str(entity_id),
            novel_id=str(novel_id),
            deps=deps,
        )
        if result is None:
            return None

        summary_data = build_summary_data(entity_id, novel_id, result)
        persisted = await wiki_repo.upsert_summary(summary_data, result)
        logger.info("wiki_summary_persisted", entity_id=str(entity_id))
        return WikiSummaryResponse.model_validate(persisted)
    except ForbiddenError:
        raise
    except Exception:
        logger.exception("wiki_generate_failed", entity_id=str(entity_id))
        return None


async def list_summaries(
    wiki_repo: WikiRepository,
    kb_repo: KBRepositoryProtocol,
    entity_ids: list[uuid.UUID] | None,
    novel_id: uuid.UUID,
) -> WikiSummaryListResponse:
    """Fetch wiki summaries and map them to the list response schema.

    M11: enriches each item with the KB entity's NAME via one batched
    KB read — the overview card previously had only the raw UUID to render.
    ``None`` for entries that no longer exist.
    """
    from narrare.kb.worldbuilding_entity_assembly import list_entities

    summaries = await wiki_repo.get_summaries(entity_ids, novel_id)
    entities = await list_entities(kb_repo, novel_id, None)
    names = {e.id: e.name for e in entities}
    items: list[WikiSummaryResponse] = []
    for s in summaries:
        # pydantic 2.13 has no ``model_validate(update=…)`` — two-step form.
        item = WikiSummaryResponse.model_validate(s)
        item.entity_name = names.get(s.entity_id)
        items.append(item)
    return WikiSummaryListResponse(items=items, total=len(items))


def compose_chapter_wiki_service(
    wiki_repo: WikiRepository,
    novel_repo: NovelRepositoryProtocol,
    chapter_repo: ChapterRepositoryProtocol,
    core: WikiServiceProtocol,
    *,
    system_mode: bool = False,
) -> ChapterWikiService:
    """Wire a ChapterWikiService for the given plane (factory-style)."""
    return ChapterWikiService(
        wiki_repo=wiki_repo,
        novel_repo=novel_repo,
        chapter_repo=chapter_repo,
        core_wiki_service=core,
        system_mode=system_mode,
    )


async def build_wiki_index(
    wiki_repo: WikiRepository,
    novel_id: uuid.UUID,
) -> WikiIndexResponse:
    """Aggregate wiki summary statuses into the overview response."""
    summaries = await wiki_repo.get_summaries(None, novel_id)
    fresh = sum(1 for s in summaries if s.status == "fresh")
    stale = sum(1 for s in summaries if s.status == "stale")
    pending = sum(1 for s in summaries if s.status == "pending")
    last_gen = max(
        (s.generated_at for s in summaries if s.generated_at),
        default=None,
    )
    return WikiIndexResponse(
        novel_id=novel_id,
        total_summaries=len(summaries),
        fresh_count=fresh,
        stale_count=stale,
        pending_count=pending,
        last_generated_at=last_gen,
    )
