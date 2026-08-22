# apps/api/narrare/notes/search_service.py
"""Semantic note search with RULE-11 lexical fallback (NOTES-001 §6a).

Flow: resolve filtered candidate note ids (lexical repository filters) →
embed the query → vector search restricted to ``source_type="note"`` and the
candidate ids → map hits back to notes with similarity scores. When no
embedding provider is configured or embedding fails, transparently fall
back to ILIKE search and report ``mode="lexical"`` — notes are ALWAYS
searchable (RULE-11). The lexical ``GET /notes?q=`` filter remains
independent (spec §6a).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.notes.schemas import (
    NoteResponse,
    NoteSearchHit,
    NoteSearchRequest,
    NoteSearchResponse,
)
from narrare_core.llm.embeddings import embed_texts
from narrare_core.settings import get_core_settings

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.embeddings.contracts import EmbeddingRepositoryProtocol
    from narrare.notes.contracts import NoteRepositoryProtocol

logger = structlog.get_logger(__name__)

#: Upper bound of candidate notes fed into the vector search after filtering.
#: Annotated governed default — same pattern as DEFAULT_EMBEDDING_SEARCH_LIMIT
#: in narrare.embeddings.contracts (RULE-18 sanctioned form).
_MAX_FILTER_CANDIDATES: int = 500


class NoteSearchService:
    """Business logic for note search (semantic + lexical fallback)."""

    def __init__(
        self,
        notes_repo: NoteRepositoryProtocol,
        embedding_repo: EmbeddingRepositoryProtocol,
        *,
        model: str | None = None,
    ) -> None:
        self._notes_repo = notes_repo
        self._embedding_repo = embedding_repo
        # Default model owned by CoreSettings (ADR-071 §3).
        self._model = model or get_core_settings().default_embedding_model

    async def search(self, user_id: UUID, request: NoteSearchRequest) -> NoteSearchResponse:
        """Search notes semantically; degrade lexically on embedding failure."""
        candidates = await self._notes_repo.list_notes(
            user_id,
            note_type=request.note_type.value if request.note_type else None,
            tag=request.tag,
            novel_id=request.novel_id,
            series_id=request.series_id,
            q=None,
            limit=_MAX_FILTER_CANDIDATES,
        )
        if not candidates:
            return await self._lexical(user_id, request)

        try:
            vectors = await embed_texts([request.query], model=self._model)
        except Exception as exc:
            logger.warning("note_semantic_search_fallback", error=str(exc))
            return await self._lexical(user_id, request)

        rows = await self._embedding_repo.search(
            vectors[0],
            source_type="note",
            source_ids={n.id for n in candidates},
            limit=request.limit,
            # Same model as the query embedding — the upsert conflict key is
            # (source_type, source_id, model), so unfiltered search could
            # return the same note twice with cross-model scores. Mirrors
            # EmbeddingService.search (embeddings/service.py).
            model=self._model,
        )
        by_id = {n.id: n for n in candidates}
        hits: list[NoteSearchHit] = []
        for row in rows:
            note = by_id.get(row.embedding.source_id)
            if note is None:
                continue
            hits.append(
                NoteSearchHit(
                    **NoteResponse.model_validate(note).model_dump(),
                    similarity=row.similarity,
                )
            )
        return NoteSearchResponse(mode="semantic", query=request.query, results=hits)

    async def _lexical(self, user_id: UUID, request: NoteSearchRequest) -> NoteSearchResponse:
        """ILIKE fallback over the same filters — always available (RULE-11)."""
        notes = await self._notes_repo.list_notes(
            user_id,
            note_type=request.note_type.value if request.note_type else None,
            tag=request.tag,
            novel_id=request.novel_id,
            series_id=request.series_id,
            q=request.query,
            limit=request.limit,
        )
        results = [
            NoteSearchHit(**NoteResponse.model_validate(n).model_dump(), similarity=None)
            for n in notes
        ]
        return NoteSearchResponse(mode="lexical", query=request.query, results=results)
