"""ProactiveContextService — 3-stage KB suggestion pipeline.

Stage 1: Name matching — which known entity names appear in the text.
Stage 2: Embedding search — semantic similarity via EmbeddingStoreProtocol.
Stage 3: Hybrid scoring — combine signals using rank_candidates().

Uses EmbeddingStoreProtocol via DI (RULE-03, RULE-07).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.context.name_matching import match_entity_names
from narrare_core.context.suggestion import EntityMetadata, Suggestion
from narrare_core.embeddings.scoring import (
    ScoredCandidate,
    ScoringConfig,
    compute_hybrid_score,
    rank_candidates,
)

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.embeddings.store import EmbeddingStoreProtocol, SearchResult

logger = structlog.get_logger(__name__)

# Boost applied to similarity when entity name is found in text
_NAME_MATCH_BOOST = 0.2

# Score boost for entities connected to name-matched entities via KB
# relationships. Lower than name-match boost because graph proximity is a
# weaker signal than a direct mention in the text.
_GRAPH_NEIGHBOR_BOOST = 0.15

# Base similarity for name-only matches (not in embedding results)
_NAME_MATCH_BASE_SIMILARITY = 0.6


class ProactiveContextService:
    """Suggest relevant KB entries based on chapter content.

    Three-stage pipeline:
    1. Name matching: Check which known entity names appear in the text.
    2. Embedding search: Find semantically similar entries via pgvector.
    3. Hybrid scoring: Rank candidates using similarity + usage + recency.

    Args:
        embedding_store: Platform-independent embedding search interface.
        scoring_config: Optional scoring configuration override.
    """

    def __init__(
        self,
        embedding_store: EmbeddingStoreProtocol,
        scoring_config: ScoringConfig | None = None,
    ) -> None:
        self._store = embedding_store
        self._scoring_config = scoring_config

    async def suggest(
        self,
        chapter_content: str,
        *,
        novel_id: UUID,
        chapter_frontmatter: dict[str, object] | None = None,
        entity_names: list[str] | None = None,
        max_results: int = 20,
        entity_metadata: dict[UUID, EntityMetadata] | None = None,
        entity_connections: dict[UUID, set[UUID]] | None = None,
    ) -> list[Suggestion]:
        """Suggest relevant KB entries for a chapter.

        Args:
            chapter_content: The chapter text to analyze.
            novel_id: Novel UUID to scope the embedding search.
            chapter_frontmatter: Optional frontmatter (currently unused, reserved).
            entity_names: Known entity names for name matching.
            max_results: Maximum suggestions to return (1-100, default 20).
            entity_metadata: Optional metadata mapping entry_id to name, type,
                usage_count, and last_referenced_at.
            entity_connections: Optional adjacency map ``entity_id -> set of
                connected entity_ids`` (from KB relationships). Entities connected
                to name-matched entities receive a similarity boost. ``None``
                disables graph boosting (graceful degradation, backward compatible).

        Returns:
            Ranked list of Suggestions sorted by relevance_score descending.
        """
        max_results = max(1, min(max_results, 100))

        # Derive entity_names from metadata if not explicitly provided
        names = entity_names
        if names is None and entity_metadata is not None:
            names = [meta.name for meta in entity_metadata.values()]

        # Stage 1: Name matching
        matched_names = match_entity_names(chapter_content, names or [])
        logger.debug(
            "name_matching_complete",
            total_names=len(names or []),
            matched=len(matched_names),
        )

        # Build name -> entry_id map from metadata
        name_to_id: dict[str, UUID] = {}
        if entity_metadata is not None:
            for entry_id, meta in entity_metadata.items():
                name_to_id[meta.name] = entry_id

        # Identify name-matched entry IDs
        matched_entry_ids: set[UUID] = set()
        for name in matched_names:
            if name in name_to_id:
                matched_entry_ids.add(name_to_id[name])

        # Stage 2: Embedding search
        search_results = await self._store.search(
            query=chapter_content,
            source_type="kb_entry",
            novel_id=novel_id,
            limit=max_results * 2,  # overfetch for dedup room
        )
        logger.debug(
            "embedding_search_complete",
            results=len(search_results),
        )

        if not search_results and not matched_entry_ids:
            return []

        # Stage 3: Build candidates and hybrid scoring
        candidates_by_id = self._build_candidates(
            search_results=search_results,
            matched_entry_ids=matched_entry_ids,
            entity_metadata=entity_metadata,
            entity_connections=entity_connections,
        )

        ranked = rank_candidates(
            list(candidates_by_id.values()),
            config=self._scoring_config,
        )

        return self._to_suggestions(
            ranked=ranked,
            matched_entry_ids=matched_entry_ids,
            entity_metadata=entity_metadata,
            max_results=max_results,
        )

    def _build_candidates(
        self,
        search_results: list[SearchResult],
        matched_entry_ids: set[UUID],
        entity_metadata: dict[UUID, EntityMetadata] | None,
        entity_connections: dict[UUID, set[UUID]] | None = None,
    ) -> dict[UUID, ScoredCandidate]:
        """Merge embedding results and name matches into scored candidates."""
        candidates: dict[UUID, ScoredCandidate] = {}

        # 3a. From embedding results
        for result in search_results:
            is_matched = result.source_id in matched_entry_ids
            similarity = min(result.score + _NAME_MATCH_BOOST, 1.0) if is_matched else result.score
            meta = entity_metadata.get(result.source_id) if entity_metadata else None
            candidates[result.source_id] = ScoredCandidate(
                source_id=result.source_id,
                source_type=result.source_type,
                similarity=similarity,
                usage_count=meta.usage_count if meta else 0,
                last_referenced_at=meta.last_referenced_at if meta else None,
                content_hash=result.content_hash,
            )

        # 3b. Name-only matches (not in embedding results)
        for entry_id in matched_entry_ids:
            if entry_id in candidates:
                continue
            meta = entity_metadata.get(entry_id) if entity_metadata else None
            if meta is None:
                continue
            candidates[entry_id] = ScoredCandidate(
                source_id=entry_id,
                source_type="kb_entry",
                similarity=_NAME_MATCH_BASE_SIMILARITY,
                usage_count=meta.usage_count,
                last_referenced_at=meta.last_referenced_at,
                content_hash="",
            )

        # 3c. Graph-neighbor boost: entities connected to name-matched entities
        # get a similarity boost (they're relevant by relationship, not just text
        # similarity). Graph boost only ELEVATES existing candidates — it never
        # creates new ones, so an entity must be both semantically relevant AND
        # graph-connected to receive the boost.
        if entity_connections:
            for matched_id in matched_entry_ids:
                for connected_id in entity_connections.get(matched_id, set()):
                    candidate = candidates.get(connected_id)
                    if candidate is None:
                        continue
                    candidate.similarity = min(candidate.similarity + _GRAPH_NEIGHBOR_BOOST, 1.0)

        return candidates

    def _to_suggestions(
        self,
        ranked: list[ScoredCandidate],
        matched_entry_ids: set[UUID],
        entity_metadata: dict[UUID, EntityMetadata] | None,
        max_results: int,
    ) -> list[Suggestion]:
        """Convert ranked candidates to Suggestion objects."""
        max_usage = max((c.usage_count for c in ranked), default=0)

        suggestions: list[Suggestion] = []
        for candidate in ranked[:max_results]:
            meta = entity_metadata.get(candidate.source_id) if entity_metadata else None
            if candidate.source_id in matched_entry_ids:
                reason = "mentioned_in_text"
            else:
                reason = "semantically_similar"

            relevance_score = compute_hybrid_score(
                candidate,
                max_usage=max_usage,
                config=self._scoring_config,
            )

            suggestions.append(
                Suggestion(
                    entry_id=candidate.source_id,
                    entry_type=meta.entity_type if meta else "unknown",
                    name=meta.name if meta else str(candidate.source_id),
                    relevance_score=relevance_score,
                    reason=reason,
                    similarity=candidate.similarity,
                    usage_count=candidate.usage_count,
                    last_referenced_at=candidate.last_referenced_at,
                )
            )

        return suggestions
