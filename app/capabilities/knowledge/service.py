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
from app.capabilities.knowledge.jobs import KIND, KIND_CHECK, MAX_NAME_LENGTH
from app.capabilities.knowledge.prompts import ENTITY_KINDS
from app.capabilities.knowledge.repository import (
    ACCEPTED,
    ACKNOWLEDGED,
    DISCARDED,
    DISMISSED,
    PENDING,
    ChunkRepository,
    ConsistencyFindingRepository,
    DocumentRepository,
    EntityRepository,
    EntitySuggestionRepository,
)
from app.capabilities.knowledge.schemas import EntityUpdate, ReembedResult
from app.kernel.auth import SetupRequiredError
from app.kernel.contracts.models import (
    Chapter,
    ConsistencyFinding,
    Document,
    Entity,
    EntitySuggestion,
    Novel,
    User,
)
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


class FindingAlreadyReviewedError(Exception):
    """The finding was acknowledged or dismissed before; review is exactly-once."""


class InvalidEntityUpdateError(ValueError):
    """The update breaks the entity contract: a blank or over-long name, or
    a kind outside the extraction vocabulary."""


class SelfMergeError(Exception):
    """The merge names its own source as the target; folding a row into
    itself is a no-op with a delete's blast radius, so it is refused."""


class CrossNovelMergeError(Exception):
    """The merge names a target in another novel; a merge folds two entries
    of one story, so the relation is invalid — the target row is neither
    missing nor the caller's to discard."""


class KnowledgeService:
    def __init__(self, session: AsyncSession, user_id: UUID, embeddings: EmbeddingProvider) -> None:
        """Bind knowledge operations to this user's session and embedding provider."""
        self.session = session
        self.user_id = user_id
        self.embeddings = embeddings
        self.documents = DocumentRepository(session, user_id)
        self.chunks = ChunkRepository(session, user_id)
        self.passages = PassageRepository(session, user_id)
        self.entities = EntityRepository(session, user_id)
        self.suggestions = EntitySuggestionRepository(session, user_id)
        self.findings = ConsistencyFindingRepository(session, user_id)

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
        The enqueue rides this transaction and becomes durable on commit.

        Commit and return the job. Raise SetupRequiredError if the user is
        missing, or NotFoundError if the novel or its chapter is not owned.
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
        """Return entities oldest first; raise NotFoundError for an absent or unowned novel."""
        await self._own_novel(novel_id)
        return await self.entities.list_for_novel(novel_id)

    async def list_suggestions(
        self, novel_id: UUID, status: str = PENDING
    ) -> Sequence[EntitySuggestion]:
        """Return suggestions in the requested review state, oldest first.

        Default to pending; raise NotFoundError for an absent or unowned novel.
        """
        await self._own_novel(novel_id)
        return await self.suggestions.list_for_novel(novel_id, status)

    async def accept_suggestion(self, suggestion_id: UUID) -> tuple[Entity, EntitySuggestion]:
        """Accept: create the entity and consume the suggestion, one transaction.

        The repository's row lock plus the pending check is the exactly-once
        guarantee: a concurrent accept waits for this commit and then reads a
        consumed row. Entity and status ride the same commit — there is no
        state in which the entity exists and the suggestion is still pending,
        nor the other way around.

        Return the entity and consumed suggestion. Raise NotFoundError for
        an absent or unowned suggestion, or AlreadyReviewedError if not pending.
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
        """Discard: consume without creating, with accept's exactly-once.

        Commit and return the suggestion. Raise NotFoundError for an absent or
        unowned suggestion, or AlreadyReviewedError if it is no longer pending.
        """
        suggestion = await self.suggestions.locked(suggestion_id)
        if suggestion is None:
            raise NotFoundError
        if suggestion.status != PENDING:
            raise AlreadyReviewedError
        suggestion.status = DISCARDED
        await self.session.commit()
        return suggestion

    async def enqueue_consistency(self, novel_id: UUID) -> Job:
        """Validate the novel and enqueue the consistency check — nothing more.

        The request only enqueues (D14): the provider call is the worker's,
        in the check's handler. The enqueue becomes durable on commit. The whole novel is the
        work — a novel without chapters is also valid to enqueue.

        Commit and return the job. Raise SetupRequiredError if the user is
        missing, or NotFoundError if the novel is absent or unowned.
        """
        if await self.session.get(User, self.user_id) is None:
            raise SetupRequiredError
        await self._own_novel(novel_id)
        job = await enqueue(self.session, self.user_id, KIND_CHECK, {"novel_id": str(novel_id)})
        await self.session.commit()
        return job

    async def list_findings(
        self, novel_id: UUID, status: str = PENDING
    ) -> Sequence[ConsistencyFinding]:
        """Return findings in the requested review state, oldest first.

        Default to pending; raise NotFoundError for an absent or unowned novel.
        """
        await self._own_novel(novel_id)
        return await self.findings.list_for_novel(novel_id, status)

    async def acknowledge_finding(self, finding_id: UUID) -> ConsistencyFinding:
        """Acknowledge: consume the finding — seen, and the text stays as it is.

        The suggestion queue's exactly-once, for the second review lane: the
        repository's row lock plus the pending check makes a concurrent
        verdict wait for this commit and then read a consumed row.

        Commit and return the finding. Raise NotFoundError for an absent or
        unowned finding, or FindingAlreadyReviewedError if no longer pending.
        """
        finding = await self.findings.locked(finding_id)
        if finding is None:
            raise NotFoundError
        if finding.status != PENDING:
            raise FindingAlreadyReviewedError
        finding.status = ACKNOWLEDGED
        await self.session.commit()
        return finding

    async def dismiss_finding(self, finding_id: UUID) -> ConsistencyFinding:
        """Dismiss: mark the finding dismissed, with acknowledge's exactly-once.

        Commit and return the retained row. Raise NotFoundError for an absent
        or unowned finding, or FindingAlreadyReviewedError if no longer pending.
        """
        finding = await self.findings.locked(finding_id)
        if finding is None:
            raise NotFoundError
        if finding.status != PENDING:
            raise FindingAlreadyReviewedError
        finding.status = DISMISSED
        await self.session.commit()
        return finding

    async def update_entity(self, entity_id: UUID, changes: EntityUpdate) -> Entity:
        """Correct an entity by hand: only the fields the body carries.

        The values are checked against the same contract the parse side
        checks — a name that is not blank and fits its column, a kind from
        the extraction vocabulary — so a hand correction can never write a
        row the review path would have refused. ``model_fields_set`` is
        what makes the update partial: a field the body does not carry is
        not a change, and a carried ``null`` description is one (the
        cleared state, not the skipped field).

        Commit and return the entity. Raise NotFoundError if it is absent or
        unowned, or InvalidEntityUpdateError for an invalid name or kind.
        """
        entity = await self.entities.get(entity_id)
        if entity is None:
            raise NotFoundError
        provided = changes.model_fields_set
        # One field at a time, validate and carry together: the
        # assignments are in-memory until the single commit below, so a
        # refusal on any field leaves the row exactly as it was.
        if "name" in provided:
            name = changes.name
            if not name or not name.strip():
                raise InvalidEntityUpdateError("an entity needs a name")
            if len(name) > MAX_NAME_LENGTH:
                raise InvalidEntityUpdateError(
                    f"an entity's name is over the {MAX_NAME_LENGTH} character limit"
                )
            entity.name = name
        if "kind" in provided:
            kind = changes.kind
            if kind not in ENTITY_KINDS:
                raise InvalidEntityUpdateError(
                    f"an entity's kind is not one of {'|'.join(ENTITY_KINDS)}"
                )
            entity.kind = kind
        if "description" in provided:
            entity.description = changes.description
        await self.session.commit()
        return entity

    async def delete_entity(self, entity_id: UUID) -> None:
        """Delete an entity: one row goes, and nothing else.

        Entity rows have no referents. An accepted suggestion keeps its own
        name/kind/description snapshot — it is a self-contained copy, never
        a reference to the entity it filed — and nothing else points at an
        entity, so the delete is a row delete: no cascade to chase, no
        orphan to leave, and the review history stays exactly as it was.

        Commit the deletion; raise NotFoundError for an absent or unowned entity.
        """
        entity = await self.entities.get(entity_id)
        if entity is None:
            raise NotFoundError
        await self.entities.delete(entity)
        await self.session.commit()

    async def merge_entities(self, source_id: UUID, target_id: UUID) -> Entity:
        """Fold the source into the target: the target survives, the source
        is deleted.

        The same no-referents fact shapes the merge: nothing hangs off
        either row that could move, so "merge" is delete-plus-keep — the
        source's row goes, the target's stays as it is. Both ends are read
        scoped to the caller: the other user's row is the same absence as
        no row, whichever end of the pair it is. Both ends must also sit in
        the same novel: a merge folds two entries of one story, so another
        novel's row is an invalid target, not a missing one.

        Commit and return the unchanged target. Raise SelfMergeError for equal
        IDs, NotFoundError for either absent or unowned row, or CrossNovelMergeError
        when the two owned entities belong to different novels.
        """
        if source_id == target_id:
            raise SelfMergeError
        source = await self.entities.get(source_id)
        if source is None:
            raise NotFoundError
        target = await self.entities.get(target_id)
        if target is None:
            raise NotFoundError
        if target.novel_id != source.novel_id:
            raise CrossNovelMergeError
        await self.entities.delete(source)
        await self.session.commit()
        return target
