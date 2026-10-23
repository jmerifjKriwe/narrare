"""Knowledge logic: ingest a text, search it, extract and review entities.

The router only translates; the unit of work lives here. Extraction is the
one thing this capability does in the background: the request enqueues the
job on its own transaction (D14) and the worker's handler — knowledge's
``jobs.py`` — does the provider call.
"""

from collections.abc import Sequence  # noqa: TC003
from uuid import UUID  # noqa: TC003

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.capabilities.knowledge.chunking import chunk_text
from app.capabilities.knowledge.jobs import KIND
from app.capabilities.knowledge.repository import (
    ACCEPTED,
    DISCARDED,
    PENDING,
    ChunkRepository,
    DocumentRepository,
    EntityRepository,
    EntitySuggestionRepository,
)
from app.capabilities.knowledge.schemas import ReembedResult
from app.kernel.auth import SetupRequiredError
from app.kernel.contracts.models import Chapter, Document, Entity, EntitySuggestion, Novel, User
from app.kernel.embeddings import EmbeddingProvider  # noqa: TC001
from app.kernel.jobs import Job, enqueue
from app.kernel.retrieval import EmbeddingMismatchError, Passage, PassageRepository

MAX_UPLOAD_BYTES = 1_000_000
"""One document, at most. Ingestion embeds in-request; an unbounded upload would
hold the worker and, with a paid provider, bill without limit."""


class EmptyDocumentError(Exception):
    """The upload carries no text to embed."""


class DocumentTooLargeError(Exception):
    """The upload is larger than MAX_UPLOAD_BYTES."""


class NotFoundError(Exception):
    """The row does not exist or belongs to another user; the two are one answer."""


class AlreadyReviewedError(Exception):
    """The suggestion was accepted or discarded before; review is exactly-once."""


class KnowledgeService:
    def __init__(self, session: AsyncSession, user_id: UUID, embeddings: EmbeddingProvider) -> None:
        self.session = session
        self.user_id = user_id
        self.embeddings = embeddings
        self.documents = DocumentRepository(session, user_id)
        self.chunks = ChunkRepository(session, user_id)
        self.passages = PassageRepository(session, user_id)
        self.entities = EntityRepository(session, user_id)
        self.suggestions = EntitySuggestionRepository(session, user_id)

    async def list_documents(self) -> Sequence[Document]:
        return await self.documents.list()

    async def ingest(self, title: str, text: str) -> Document:
        if len(text.encode("utf-8")) > MAX_UPLOAD_BYTES:
            raise DocumentTooLargeError
        if await self.session.get(User, self.user_id) is None:
            raise SetupRequiredError
        chunks = chunk_text(text)
        if not chunks:
            raise EmptyDocumentError
        vectors = await self.embeddings.embed(chunks)
        width = len(vectors[0])
        stored = await self.passages.stored_width()
        if stored is not None and stored != width:
            raise EmbeddingMismatchError(stored, width)
        document = await self.documents.create(title, width)
        await self.chunks.create_many(document.id, chunks, vectors)
        await self.session.commit()
        return document

    async def search(self, query: str, limit: int) -> Sequence[Passage]:
        [vector] = await self.embeddings.embed([query])
        return await self.passages.search(vector, limit)

    async def reembed(self) -> ReembedResult:
        """Re-embed every chunk through the configured model.

        The fix the mismatch refusal asks for: chunk texts are stored, so this is
        a pure data operation — no upload, no schema change. The corpus ends at
        one width again, the one the configured model answers with.
        """
        if await self.session.get(User, self.user_id) is None:
            raise SetupRequiredError
        documents = await self.documents.list()
        chunk_count = 0
        for document in documents:
            chunks = await self.chunks.of_document(document.id)
            if not chunks:
                continue
            vectors = await self.embeddings.embed([chunk.text for chunk in chunks])
            for chunk, vector in zip(chunks, vectors, strict=True):
                chunk.embedding = list(vector)
            document.embedding_width = len(vectors[0])
            chunk_count += len(chunks)
        await self.session.commit()
        return ReembedResult(documents=len(documents), chunks=chunk_count)

    async def _own_novel(self, novel_id: UUID) -> Novel:
        """The novel or NotFoundError — every list below answers per novel.

        Reading the novel through the kernel models is the sanctioned seam:
        novels and chapters are shared domain, whichever capability owns their
        write paths."""
        novel = await self.session.scalar(
            select(Novel).where(Novel.id == novel_id, Novel.user_id == self.user_id)
        )
        if novel is None:
            raise NotFoundError
        return novel

    async def enqueue_extraction(self, novel_id: UUID, chapter_id: UUID) -> Job:
        """Validate the chapter and enqueue the extraction job — nothing more.

        The request only enqueues (D14): the provider call is the worker's.
        The enqueue rides this transaction, so a failure of the request leaves
        no job behind.
        """
        if await self.session.get(User, self.user_id) is None:
            raise SetupRequiredError
        await self._own_novel(novel_id)
        chapter = await self.session.scalar(
            select(Chapter).where(
                Chapter.id == chapter_id,
                Chapter.novel_id == novel_id,
                Chapter.user_id == self.user_id,
            )
        )
        if chapter is None:
            raise NotFoundError
        job = await enqueue(self.session, self.user_id, KIND, {"chapter_id": str(chapter_id)})
        await self.session.commit()
        return job

    async def list_entities(self, novel_id: UUID) -> Sequence[Entity]:
        await self._own_novel(novel_id)
        return await self.entities.list_for_novel(novel_id)

    async def list_suggestions(
        self, novel_id: UUID, status: str = PENDING
    ) -> Sequence[EntitySuggestion]:
        await self._own_novel(novel_id)
        return await self.suggestions.list_for_novel(novel_id, status)

    async def accept_suggestion(self, suggestion_id: UUID) -> tuple[Entity, EntitySuggestion]:
        """Accept: create the entity and consume the suggestion, one transaction.

        The repository's row lock plus the pending check is the exactly-once
        guarantee: a concurrent accept waits for this commit and then reads a
        consumed row. Entity and status ride the same commit — there is no
        state in which the entity exists and the suggestion is still pending,
        nor the other way around.
        """
        suggestion = await self.suggestions.locked(suggestion_id)
        if suggestion is None:
            raise NotFoundError
        if suggestion.status != PENDING:
            raise AlreadyReviewedError
        entity = await self.entities.create(
            suggestion.novel_id, suggestion.name, suggestion.kind, suggestion.description
        )
        suggestion.status = ACCEPTED
        await self.session.commit()
        return entity, suggestion

    async def discard_suggestion(self, suggestion_id: UUID) -> EntitySuggestion:
        """Discard: consume without creating, with accept's exactly-once."""
        suggestion = await self.suggestions.locked(suggestion_id)
        if suggestion is None:
            raise NotFoundError
        if suggestion.status != PENDING:
            raise AlreadyReviewedError
        suggestion.status = DISCARDED
        await self.session.commit()
        return suggestion
