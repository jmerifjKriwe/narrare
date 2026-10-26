"""Knowledge logic: ingest a text, search it, extract and review entities.

The router only translates; the unit of work lives here. Extraction is the
one thing this capability does in the background: the request enqueues the
job on its own transaction (D14) and the worker's handler — knowledge's
``jobs.py`` — does the provider call.
"""

from collections.abc import Sequence  # noqa: TC003
from typing import NamedTuple
from uuid import UUID  # noqa: TC003

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.capabilities.knowledge.chunking import chunk_text
from app.capabilities.knowledge.jobs import KIND, KIND_CHECK, MAX_NAME_LENGTH
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
    RelationRepository,
    entity_search_text,
)
from app.capabilities.knowledge.schemas import EntityUpdate, ReembedResult, RelationPatch
from app.kernel.auth import SetupRequiredError
from app.kernel.contracts.models import (
    ENTITY_TYPES,
    Chapter,
    ConsistencyFinding,
    Document,
    Entity,
    EntityRelation,
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

EMBEDDING_CONTENT_LIMIT = 20_000
"""The most body an embedding text carries, in characters (D5). The cap is
for the vector only: storage keeps the full body."""

MAX_LABEL_LENGTH = 200
"""The width an alias or tag may carry, the name column's own limit."""


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
    """The update breaks the entity contract: a blank or over-long name, a
    type outside the extraction vocabulary, or a blank or over-long alias
    or tag."""


class SelfMergeError(Exception):
    """The merge names its own source as the target; folding a row into
    itself is a no-op with a delete's blast radius, so it is refused."""


class CrossNovelMergeError(Exception):
    """The merge names a target in another novel; a merge folds two entries
    of one story, so the relation is invalid — the target row is neither
    missing nor the caller's to discard."""


class InvalidRelationError(ValueError):
    """The relation breaks its contract: a blank or over-long relation_type."""


class RelationExistsError(Exception):
    """The same directed edge between the same two rows already carries
    this relation_type; the edge, not the wording, is the duplicate."""


class SkippedRelation(NamedTuple):
    """A proposed relation accept could not place, with the proposal's own
    words: the target's name as proposed and the relation's type. The skip
    is transient — the accept response carries it once (D8), nothing
    persists it."""

    target_name: str
    relation_type: str


def _embedding_text(entity: Entity) -> str:
    """The text a vector is built from: identity words, then the body.

    The body is capped for the vector only (D5) — storage keeps everything.
    """
    return " ".join(
        [
            entity.name,
            *entity.aliases,
            *entity.tags,
            entity.content[:EMBEDDING_CONTENT_LIMIT],
        ]
    )


def _clean_labels(values: list[str] | None, what: str) -> list[str]:
    """Aliases or tags as the contract stores them: stripped, each nonblank
    and at most MAX_LABEL_LENGTH, deduped case-insensitively (first spelling
    wins). No count limit — a writer's novel, not a form."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        label = value.strip()
        if not label:
            raise InvalidEntityUpdateError(f"an entity's {what} cannot be blank")
        if len(label) > MAX_LABEL_LENGTH:
            raise InvalidEntityUpdateError(
                f"an entity's {what} is over the {MAX_LABEL_LENGTH} character limit"
            )
        folded = label.casefold()
        if folded not in seen:
            seen.add(folded)
            cleaned.append(label)
    return cleaned


def _union_labels(
    base: list[str], additions: Sequence[str], *, taken: Sequence[str] = ()
) -> list[str]:
    """Base labels then the additions not already there, case-insensitively —
    the merge's union, order-stable: the survivor's words keep their order.
    ``taken`` seeds the set with words owned elsewhere, so an addition that
    spells one is dropped: the survivor's own name is not its alias."""
    seen = {label.casefold() for label in base}
    seen.update(label.casefold() for label in taken)
    union = list(base)
    for label in additions:
        folded = label.casefold()
        if folded not in seen:
            seen.add(folded)
            union.append(label)
    return union


# The SQLSTATE of a unique violation. The create backstop reads it off the
# driver's original error to tell the two races apart: a concurrent create of
# the same edge is the duplicate's verdict, a foreign key's is the absence's.
UNIQUE_VIOLATION = "23505"


def _validate_relation_type(relation_type: str | None) -> str:
    """The relation_type the contract stores: nonblank, at most 80 characters,
    stripped — the stored form is the edge's identity, so a padded twin must
    not dodge the duplicate check by its whitespace."""
    if relation_type is None or not relation_type.strip():
        raise InvalidRelationError("a relation needs a type")
    if len(relation_type) > 80:
        raise InvalidRelationError("a relation's type is over the 80 character limit")
    return relation_type.strip()


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
        self.relations = RelationRepository(session, user_id)
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

    async def _embed_entity(self, entity: Entity) -> None:
        """Embed one entity in the request's transaction, guarded like upload.

        The corpus keeps one width: the first set vector's width is the
        user's, and a model that answers at another width is a refusal that
        names the fix (EmbeddingMismatchError, HTTP 409) — never silently
        degraded search. The assignments stay in-memory until the caller's
        single commit, so a refusal leaves the row exactly as it was.
        """
        [vector] = await self.embeddings.embed([_embedding_text(entity)])
        stored = await self.entities.stored_entity_width()
        if stored is not None and stored != len(vector):
            raise EmbeddingMismatchError(stored, len(vector))
        entity.embedding = vector

    async def list_entities(
        self, novel_id: UUID, type: str | None = None, tag: str | None = None, q: str | None = None
    ) -> Sequence[Entity]:
        """The novel's entities, filtered by type and tag or fuzzy-found by
        q (the trigram tier over search_text); raise NotFoundError for an
        absent or unowned novel."""
        await self._own_novel(novel_id)
        return await self.entities.list_for_novel(novel_id, type=type, tag=tag, q=q)

    async def list_suggestions(
        self, novel_id: UUID, status: str = PENDING
    ) -> Sequence[EntitySuggestion]:
        """Return suggestions in the requested review state, oldest first.

        Default to pending; raise NotFoundError for an absent or unowned novel.
        """
        await self._own_novel(novel_id)
        return await self.suggestions.list_for_novel(novel_id, status)

    async def accept_suggestion(self, suggestion_id: UUID) -> tuple[Entity, list[SkippedRelation]]:
        """Accept: create the entity, place its proposed relations, and consume
        the suggestion, one transaction.

        The repository's row lock plus the pending check is the exactly-once
        guarantee: a concurrent accept waits for this commit and then reads a
        consumed row. Entity, edges and status ride the same commit — there
        is no state in which the entity exists and the suggestion is still
        pending, nor the other way around. Birth per D5: the description
        becomes the body, aliases and tags start empty, and the search text
        and the vector are computed before the commit. The proposals resolve
        per D8: trimmed, case-insensitive exact match against the novel's
        existing entities' names and aliases, the just-created entity
        included; multiple matches mean ambiguous, no match means absent,
        and both skip — the note rides the response only, nothing persists
        it.

        Return the entity and the skipped proposals. Raise NotFoundError for
        an absent or unowned suggestion, AlreadyReviewedError if not pending,
        or EmbeddingMismatchError when the configured model answers at
        another width than the entity corpus was embedded at.
        """
        suggestion = await self.suggestions.locked(suggestion_id)
        if suggestion is None:
            raise NotFoundError
        if suggestion.status != PENDING:
            raise AlreadyReviewedError
        entity = await self.entities.create(
            suggestion.novel_id,
            suggestion.name,
            suggestion.type,
            suggestion.description or "",
            aliases=[],
            tags=[],
            embedding=None,
        )
        await self._embed_entity(entity)
        skipped = await self._resolve_proposals(entity, suggestion)
        suggestion.status = ACCEPTED
        await self.session.commit()
        return entity, skipped

    async def _resolve_proposals(
        self, entity: Entity, suggestion: EntitySuggestion
    ) -> list[SkippedRelation]:
        """Place the suggestion's proposals as edges from the new entity.

        Every target resolves against the novel's existing entities — names
        and aliases, trimmed and case-insensitively, the just-created entity
        included, so a proposal may name its own origin. Exactly one match
        places the edge (a repeated proposal folds into the look-before-write);
        several matches are ambiguous and none is absent — both skip with the
        proposal's own words. The type goes through the manual path's
        validation, so the stored form is the same stripped identity an edge
        added by hand would carry.
        """
        candidates = await self.entities.list_for_novel(suggestion.novel_id)
        by_name: dict[str, list[Entity]] = {}
        by_alias: dict[str, list[Entity]] = {}
        for candidate in candidates:
            by_name.setdefault(candidate.name.strip().casefold(), []).append(candidate)
            for alias in candidate.aliases:
                by_alias.setdefault(alias.strip().casefold(), []).append(candidate)
        skipped: list[SkippedRelation] = []
        for proposal in suggestion.relations:
            target_name = str(proposal.get("target", ""))
            key = target_name.strip().casefold()
            relation_type = _validate_relation_type(str(proposal.get("type", "")))
            matches = {row.id: row for row in [*by_name.get(key, []), *by_alias.get(key, [])]}
            if len(matches) != 1:
                skipped.append(SkippedRelation(target_name, relation_type))
                continue
            target = next(iter(matches.values()))
            if await self.relations.edge(entity.id, target.id, relation_type) is None:
                await self.relations.create(entity.id, target.id, relation_type, None)
        return skipped

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
        checks — a name that is not blank and fits its column, a type from
        the extraction vocabulary, aliases and tags each nonblank and at
        most 200 characters, deduped case-insensitively — so a hand
        correction can never write a row the review path would have
        refused. ``model_fields_set`` is what makes the update partial: a
        field the body does not carry is not a change, and a carried
        ``null`` content is one (the cleared state, not the skipped field).
        A write that moves the identity words or the body recomputes
        search_text and the vector (D5), guarded like upload.

        Commit and return the entity. Raise NotFoundError if it is absent or
        unowned, InvalidEntityUpdateError for an invalid name, type, alias
        or tag, or EmbeddingMismatchError when the configured model answers
        at another width than the entity corpus was embedded at.
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
        if "type" in provided:
            type_ = changes.type
            if type_ not in ENTITY_TYPES:
                raise InvalidEntityUpdateError(
                    f"an entity's type is not one of {'|'.join(ENTITY_TYPES)}"
                )
            entity.type = type_
        if "aliases" in provided:
            entity.aliases = _clean_labels(changes.aliases, "alias")
        if "tags" in provided:
            entity.tags = _clean_labels(changes.tags, "tag")
        if "content" in provided:
            entity.content = changes.content or ""
        if provided & {"name", "aliases", "tags", "content"}:
            # the identity words or the body moved: search_text and the
            # vector ride the same commit (D5). A type change alone moves
            # neither, so it is a plain column write.
            entity.search_text = entity_search_text(entity.name, entity.aliases, entity.tags)
            await self._embed_entity(entity)
        await self.session.commit()
        return entity

    async def delete_entity(self, entity_id: UUID) -> None:
        """Delete an entity: the row goes, and its edges go with it.

        An accepted suggestion keeps its own name/type/description snapshot —
        it is a self-contained copy, never a reference to the entity it
        filed — so the review history outlives the entity. The relations'
        foreign keys cascade (D4): a hard delete takes the edges along, and
        the export is the safety net.

        Commit the deletion; raise NotFoundError for an absent or unowned entity.
        """
        entity = await self.entities.get(entity_id)
        if entity is None:
            raise NotFoundError
        await self.entities.delete(entity)
        await self.session.commit()

    async def entity_relations(self, entity_id: UUID) -> Sequence[EntityRelation]:
        """The entity's edges, both directions, oldest first.

        Raise NotFoundError for an absent or unowned entity — another
        user's rows are the same absence, including their edges.
        """
        entity = await self.entities.get(entity_id)
        if entity is None:
            raise NotFoundError
        return await self.relations.list_for_entity(entity_id)

    async def add_relation(
        self, entity_id: UUID, to_entity_id: UUID, relation_type: str, note: str | None
    ) -> EntityRelation:
        """Create a directed edge from this entity to another of the same novel.

        Self-relations are allowed — flagging them is the UI's business.
        The type is free text, checked only for blankness and length (D7);
        the exact duplicate — same owner, same ends, same type — is a
        RelationExistsError, both as the look-before-write and as the
        unique constraint's race backstop. The ends are fixed at birth:
        moving an edge is delete plus create.

        Commit and return the edge. Raise NotFoundError when either end is
        absent or unowned or not of this novel, InvalidRelationError for a
        blank or over-long type, or RelationExistsError for the duplicate.
        """
        entity = await self.entities.get(entity_id)
        if entity is None:
            raise NotFoundError
        # The target must be an owned entity of the same story: an edge
        # joins one novel, so any other answer is the scoped absence.
        target = await self.session.scalar(
            select(Entity).where(
                Entity.id == to_entity_id,
                Entity.user_id == self.user_id,
                Entity.novel_id == entity.novel_id,
            )
        )
        if target is None:
            raise NotFoundError
        checked = _validate_relation_type(relation_type)
        if await self.relations.edge(entity_id, to_entity_id, checked) is not None:
            raise RelationExistsError
        try:
            relation = await self.relations.create(entity_id, to_entity_id, checked, note)
        except IntegrityError as error:
            # The constraint caught what the look-before-write missed. The two
            # races wear different answers, told apart by the violated
            # constraint: a concurrent create of the same edge is the unique
            # violation's duplicate 409; a target deleted mid-race fails the
            # foreign key and is the scoped absence's 404. The rollback gives
            # the session back clean; this request has written nothing else.
            await self.session.rollback()
            if getattr(error.orig, "sqlstate", None) == UNIQUE_VIOLATION:
                raise RelationExistsError from None
            raise NotFoundError from None
        await self.session.commit()
        return relation

    async def update_relation(self, relation_id: UUID, changes: RelationPatch) -> EntityRelation:
        """Retype or re-note an edge; the ends stay as they are.

        ``model_fields_set`` is what makes the patch partial, the way the
        entity update's is: a carried ``null`` note clears it, an absent
        field is not a change. A changed type may not collide with the
        edge's own sibling — the same uniqueness as creation.

        Commit and return the edge. Raise NotFoundError for an absent or
        unowned edge, InvalidRelationError for a blank or over-long type,
        or RelationExistsError when the new type would duplicate a sibling.
        """
        relation = await self.relations.get(relation_id)
        if relation is None:
            raise NotFoundError
        provided = changes.model_fields_set
        if "relation_type" in provided:
            checked = _validate_relation_type(changes.relation_type)
            if checked != relation.relation_type:
                sibling = await self.relations.edge(
                    relation.from_entity_id, relation.to_entity_id, checked
                )
                if sibling is not None:
                    raise RelationExistsError
            relation.relation_type = checked
        if "note" in provided:
            relation.note = changes.note
        try:
            await self.session.commit()
        except IntegrityError:
            # The constraint caught what the look-before-write missed: a
            # concurrent retype that gave the sibling edge this request's new
            # type between its look and its commit. The rollback gives the
            # session back clean; a retype writes nothing else. The ends are
            # immutable, so no foreign key can fire here — the unique
            # violation's duplicate 409 is the whole backstop.
            await self.session.rollback()
            raise RelationExistsError from None
        return relation

    async def delete_relation(self, relation_id: UUID) -> None:
        """Delete one edge: exactly the edge, nothing else.

        Commit the deletion; raise NotFoundError for an absent or unowned edge.
        """
        relation = await self.relations.get(relation_id)
        if relation is None:
            raise NotFoundError
        await self.relations.delete(relation)
        await self.session.commit()

    async def merge_entities(self, source_id: UUID, target_id: UUID) -> Entity:
        """Fold the source into the target: the target survives, the source
        is deleted, and nothing the source carried is dropped (D3).

        The edges re-point first, both directions, and only exact
        duplicates are dropped — an edge whose re-pointed form collides
        with one the survivor already carries (or with an earlier
        re-pointed edge, oldest first) goes, every other edge moves and a
        re-pointed self-edge stays as the survivor's own. The fields fold:
        the source's name becomes an alias of the survivor — the differing
        name is why both rows existed — aliases and tags union
        (case-insensitively), the source's body is appended under a
        ``## <source name>`` heading when it is non-empty, and the
        survivor's type wins. Then search_text and the vector are
        recomputed for the folded row (D5), guarded like upload.

        Both ends are read scoped to the caller: the other user's row is
        the same absence as no row, whichever end of the pair it is. Both
        ends must also sit in the same novel: a merge folds two entries of
        one story, so another novel's row is an invalid target, not a
        missing one.

        Commit and return the folded target. Raise SelfMergeError for equal
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

        # Edges first: the dedupe runs inside this transaction, before the
        # re-pointed rows are written — the unique constraint stays a
        # backstop, not the merge's arithmetic. The surviving edge of a
        # collision is the oldest, so the fold is deterministic.
        source_edges = await self.relations.list_for_entity(source.id)
        target_edges = await self.relations.list_for_entity(target.id)
        occupied = {
            (edge.from_entity_id, edge.to_entity_id, edge.relation_type) for edge in target_edges
        }
        for edge in source_edges:
            moved_from = target.id if edge.from_entity_id == source.id else edge.from_entity_id
            moved_to = target.id if edge.to_entity_id == source.id else edge.to_entity_id
            if (moved_from, moved_to, edge.relation_type) in occupied:
                await self.relations.delete(edge)
                continue
            occupied.add((moved_from, moved_to, edge.relation_type))
            edge.from_entity_id = moved_from
            edge.to_entity_id = moved_to

        # The fields, per D3: name to alias, unions, body under a heading,
        # the survivor's type untouched. The survivor's own name seeds the
        # alias dedupe: two rows of one name fold without aliasing the name
        # to itself.
        target.aliases = _union_labels(
            target.aliases, [*source.aliases, source.name], taken=[target.name]
        )
        target.tags = _union_labels(target.tags, source.tags)
        if source.content.strip():
            # The heading opens the fold: a survivor without a body starts at
            # the heading, no leading blank lines before it.
            folded = f"## {source.name}\n\n{source.content}"
            target.content = (
                folded if not target.content.strip() else f"{target.content}\n\n{folded}"
            )
        target.search_text = entity_search_text(target.name, target.aliases, target.tags)
        await self._embed_entity(target)
        await self.entities.delete(source)
        await self.session.commit()
        return target
