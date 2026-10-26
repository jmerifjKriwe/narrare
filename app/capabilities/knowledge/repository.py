"""Document, chunk, entity, relation and suggestion persistence. All scoped to one user."""

from collections.abc import Sequence  # noqa: TC003
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from sqlalchemy import func, select

from app.kernel.contracts.models import (
    Chunk,
    ConsistencyFinding,
    Document,
    Entity,
    EntityRelation,
    EntitySuggestion,
)
from app.kernel.db.base import ScopedRepository

if TYPE_CHECKING:
    from app.capabilities.knowledge.prompts import ParsedEntity, ParsedFinding

# The review contract's three states. A suggestion is born pending and is
# consumed exactly once — accepted or discarded — by the service, in one
# transaction; these are the only values the status column ever carries.
PENDING = "pending"
ACCEPTED = "accepted"
DISCARDED = "discarded"

# The finding queue's consumed states; a finding is born pending too, and is
# consumed by acknowledge or dismiss — the same contract, its own words.
ACKNOWLEDGED = "acknowledged"
DISMISSED = "dismissed"

ENTITY_SEARCH_THRESHOLD = 0.5
"""The word_similarity floor of the list's ``q`` tier (D6: measured against
realistic misspellings, starting at 0.5 — the plain-similarity 0.8 of the
dedup tier would not find Katharina typed as Kathrina)."""


def entity_search_text(name: str, aliases: Sequence[str], tags: Sequence[str]) -> str:
    """The maintained concatenation the ``q`` tier searches: identity words.

    One writer keeps the column honest: the repository computes it on
    create, and the service recomputes it on every write that moves the
    identity words (update, merge).
    """
    return " ".join([name, *aliases, *tags])


class DocumentRepository(ScopedRepository[Document]):
    model = Document

    async def list(self) -> Sequence[Document]:
        result = await self.session.scalars(self.query().order_by(Document.created_at.desc()))
        return result.all()

    async def create(self, title: str, embedding_width: int) -> Document:
        document = Document(user_id=self.user_id, title=title, embedding_width=embedding_width)
        self.session.add(document)
        await self.session.flush()
        return document


class ChunkRepository(ScopedRepository[Chunk]):
    model = Chunk

    async def of_document(self, document_id: UUID) -> Sequence[Chunk]:
        """The document's chunks, in reading order."""
        result = await self.session.scalars(
            self.query().where(Chunk.document_id == document_id).order_by(Chunk.position)
        )
        return result.all()

    async def create_many(
        self,
        document_id: UUID,
        texts: Sequence[str],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        for position, (text, vector) in enumerate(zip(texts, vectors, strict=True)):
            self.session.add(
                Chunk(
                    user_id=self.user_id,
                    document_id=document_id,
                    position=position,
                    text=text,
                    embedding=list(vector),
                )
            )
        await self.session.flush()


class EntityRepository(ScopedRepository[Entity]):
    model = Entity

    async def get(self, entity_id: UUID) -> Entity | None:
        """The row, scoped: another user's entity answers as absent, the
        way every scoped read in this product answers."""
        return await self.session.scalar(self.query().where(Entity.id == entity_id))

    async def list_for_novel(
        self,
        novel_id: UUID,
        *,
        type: str | None = None,
        tag: str | None = None,
        q: str | None = None,
    ) -> Sequence[Entity]:
        """This user's entities in the novel: oldest first, or — when ``q``
        carries words — ranked by trigram similarity against search_text.

        ``type`` and ``tag`` are exact filters, the tag as JSONB containment.
        The ``q`` tier folds case and diacritics on both sides and keeps
        every row whose word similarity reaches the threshold; the plain
        created_at order stays the answer when nothing narrows it. The
        unaccented expression scans at novel scale, so the index stays a
        plain gin_trgm_ops on the column (§9.1).
        """
        statement = self.query().where(Entity.novel_id == novel_id)
        if type:
            statement = statement.where(Entity.type == type)
        if tag:
            statement = statement.where(Entity.tags.contains([tag]))
        needle = (q or "").strip()
        if needle:
            similarity = func.word_similarity(
                func.unaccent(func.lower(needle)),
                func.unaccent(func.lower(Entity.search_text)),
            )
            statement = statement.where(similarity >= ENTITY_SEARCH_THRESHOLD).order_by(
                similarity.desc(), Entity.created_at
            )
        else:
            statement = statement.order_by(Entity.created_at)
        result = await self.session.scalars(statement)
        return result.all()

    async def create(
        self,
        novel_id: UUID,
        name: str,
        type: str,
        content: str,
        aliases: Sequence[str],
        tags: Sequence[str],
        embedding: Sequence[float] | None,
    ) -> Entity:
        """Flush a new entity for this user without committing the transaction.

        ``search_text`` is computed here from the identity words — the one
        writer, so the column cannot drift from name, aliases and tags.
        """
        entity = Entity(
            user_id=self.user_id,
            novel_id=novel_id,
            name=name,
            type=type,
            content=content,
            aliases=list(aliases),
            tags=list(tags),
            search_text=entity_search_text(name, aliases, tags),
            embedding=list(embedding) if embedding is not None else None,
        )
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: Entity) -> None:
        """Mark the supplied entity for deletion; the caller commits the change."""
        await self.session.delete(entity)

    async def stored_entity_width(self) -> int | None:
        """The width the user's entities were embedded at; None when none is.

        The entity corpus keeps the document guard's rule: one embedding
        model per user, so the first set vector's width is the corpus's.
        Rows without a vector are honest nulls and say nothing about width.
        """
        result = await self.session.scalars(
            select(Entity.embedding)
            .where(Entity.user_id == self.user_id, Entity.embedding.is_not(None))
            .order_by(Entity.created_at)
            .limit(1)
        )
        widths = [len(vector) for vector in result.all() if vector is not None]
        return widths[0] if widths else None


class RelationRepository(ScopedRepository[EntityRelation]):
    model = EntityRelation

    async def get(self, relation_id: UUID) -> EntityRelation | None:
        """The edge, scoped: another user's relation answers as absent, the
        way every scoped read in this product answers."""
        return await self.session.scalar(self.query().where(EntityRelation.id == relation_id))

    async def list_for_entity(self, entity_id: UUID) -> Sequence[EntityRelation]:
        """The entity's edges, both directions, oldest first."""
        result = await self.session.scalars(
            self.query()
            .where(
                (EntityRelation.from_entity_id == entity_id)
                | (EntityRelation.to_entity_id == entity_id)
            )
            .order_by(EntityRelation.created_at)
        )
        return result.all()

    async def edge(
        self, from_entity_id: UUID, to_entity_id: UUID, relation_type: str
    ) -> EntityRelation | None:
        """The exact edge, scoped: the duplicate check's look-before-write."""
        return await self.session.scalar(
            self.query().where(
                EntityRelation.from_entity_id == from_entity_id,
                EntityRelation.to_entity_id == to_entity_id,
                EntityRelation.relation_type == relation_type,
            )
        )

    async def create(
        self,
        from_entity_id: UUID,
        to_entity_id: UUID,
        relation_type: str,
        note: str | None,
    ) -> EntityRelation:
        """Flush a new edge for this user without committing the transaction."""
        relation = EntityRelation(
            user_id=self.user_id,
            from_entity_id=from_entity_id,
            to_entity_id=to_entity_id,
            relation_type=relation_type,
            note=note,
        )
        self.session.add(relation)
        await self.session.flush()
        return relation

    async def delete(self, relation: EntityRelation) -> None:
        """Mark the supplied edge for deletion; the caller commits the change."""
        await self.session.delete(relation)


class EntitySuggestionRepository(ScopedRepository[EntitySuggestion]):
    model = EntitySuggestion

    async def list_for_novel(self, novel_id: UUID, status: str) -> Sequence[EntitySuggestion]:
        """Return this user's suggestions in the given review state, oldest first."""
        result = await self.session.scalars(
            self.query()
            .where(EntitySuggestion.novel_id == novel_id, EntitySuggestion.status == status)
            .order_by(EntitySuggestion.created_at)
        )
        return result.all()

    async def create_many(
        self, novel_id: UUID, chapter_id: UUID, entities: Sequence[ParsedEntity]
    ) -> None:
        """File one suggestion per parsed entity, all pending review.

        The dedupe ruling: a parsed entity whose (chapter, name, type) is
        already pending files nothing — a re-run, the outage retry's shape,
        answers with the rows the queue already holds instead of stacking a
        second set behind them. The skip reads only pending rows, which is
        the asymmetry by design: accept or discard consumes a suggestion,
        so after a review the same key files fresh on the next run — the
        writer's decision is the only thing that reopens a filed key.
        """
        result = await self.session.scalars(
            self.query().where(
                EntitySuggestion.chapter_id == chapter_id,
                EntitySuggestion.status == PENDING,
            )
        )
        # The set is the filed identity: what the query found still pending,
        # joined by every key this run files — a provider answer naming the
        # same (name, type) twice is one suggestion, not two.
        filed = {(row.name, row.type) for row in result.all()}
        for entity in entities:
            key = (entity.name, entity.type)
            if key in filed:
                continue
            filed.add(key)
            self.session.add(
                EntitySuggestion(
                    user_id=self.user_id,
                    novel_id=novel_id,
                    chapter_id=chapter_id,
                    name=entity.name,
                    type=entity.type,
                    description=entity.description,
                    # the proposals ride the row exactly as parsed — accept
                    # resolves them; the JSON speaks the answer's own keys
                    relations=[
                        {"target": relation.target, "type": relation.relation_type}
                        for relation in entity.relations
                    ],
                    status=PENDING,
                )
            )
        await self.session.flush()

    async def locked(self, suggestion_id: UUID) -> EntitySuggestion | None:
        """The suggestion with its row lock taken (SELECT ... FOR UPDATE).

        Review is exactly-once, and the guarantee must hold for two requests
        in flight at once, not just two sequential ones. The lock makes the
        second transaction wait for the first one's commit and then read the
        consumed status — one winner, one refusal — where two plain reads
        would both see ``pending`` and both consume.
        """
        return await self.session.scalar(
            self.query().where(EntitySuggestion.id == suggestion_id).with_for_update()
        )


class ConsistencyFindingRepository(ScopedRepository[ConsistencyFinding]):
    model = ConsistencyFinding

    async def list_for_novel(self, novel_id: UUID, status: str) -> Sequence[ConsistencyFinding]:
        """Return this user's findings in the given review state, oldest first."""
        result = await self.session.scalars(
            self.query()
            .where(ConsistencyFinding.novel_id == novel_id, ConsistencyFinding.status == status)
            .order_by(ConsistencyFinding.created_at)
        )
        return result.all()

    async def create_many(self, novel_id: UUID, findings: Sequence[ParsedFinding]) -> None:
        """File one finding per parsed contradiction, all pending review.

        The dedupe ruling, mirroring the suggestion queue's: a parsed finding
        whose summary is already pending files nothing — a re-run, the outage
        retry's shape, answers with the rows the queue already holds instead
        of stacking a second set behind them. The skip reads only pending
        rows, which is the asymmetry by design: acknowledge or dismiss
        consumes a finding, so after a review the same summary files fresh on
        the next run — the writer's decision is the only thing that reopens a
        filed summary.
        """
        result = await self.session.scalars(
            self.query().where(
                ConsistencyFinding.novel_id == novel_id,
                ConsistencyFinding.status == PENDING,
            )
        )
        # The set is the filed identity: what the query found still pending,
        # joined by every summary this run files — a provider answer naming
        # the same contradiction twice is one finding, not two.
        filed = {row.summary for row in result.all()}
        for finding in findings:
            if finding.summary in filed:
                continue
            filed.add(finding.summary)
            self.session.add(
                ConsistencyFinding(
                    user_id=self.user_id,
                    novel_id=novel_id,
                    summary=finding.summary,
                    detail=finding.detail,
                    status=PENDING,
                )
            )
        await self.session.flush()

    async def locked(self, finding_id: UUID) -> ConsistencyFinding | None:
        """The finding with its row lock taken (SELECT ... FOR UPDATE) —
        the suggestion queue's exactly-once guarantee, for the finding's
        acknowledge and dismiss."""
        return await self.session.scalar(
            self.query().where(ConsistencyFinding.id == finding_id).with_for_update()
        )
