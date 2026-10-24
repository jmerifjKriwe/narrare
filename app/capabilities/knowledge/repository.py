"""Document and chunk persistence. Both scoped to one user."""

from collections.abc import Sequence  # noqa: TC003
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from app.kernel.contracts.models import Chunk, Document, Entity, EntitySuggestion
from app.kernel.db.base import ScopedRepository

if TYPE_CHECKING:
    from app.capabilities.knowledge.prompts import ParsedEntity

# The review contract's three states. A suggestion is born pending and is
# consumed exactly once — accepted or discarded — by the service, in one
# transaction; these are the only values the status column ever carries.
PENDING = "pending"
ACCEPTED = "accepted"
DISCARDED = "discarded"


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

    async def list_for_novel(self, novel_id: UUID) -> Sequence[Entity]:
        result = await self.session.scalars(
            self.query().where(Entity.novel_id == novel_id).order_by(Entity.created_at)
        )
        return result.all()

    async def create(self, novel_id: UUID, name: str, kind: str, description: str | None) -> Entity:
        entity = Entity(
            user_id=self.user_id,
            novel_id=novel_id,
            name=name,
            kind=kind,
            description=description,
        )
        self.session.add(entity)
        await self.session.flush()
        return entity


class EntitySuggestionRepository(ScopedRepository[EntitySuggestion]):
    model = EntitySuggestion

    async def list_for_novel(self, novel_id: UUID, status: str) -> Sequence[EntitySuggestion]:
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

        The dedupe ruling: a parsed entity whose (chapter, name, kind) is
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
        # same (name, kind) twice is one suggestion, not two.
        filed = {(row.name, row.kind) for row in result.all()}
        for entity in entities:
            key = (entity.name, entity.kind)
            if key in filed:
                continue
            filed.add(key)
            self.session.add(
                EntitySuggestion(
                    user_id=self.user_id,
                    novel_id=novel_id,
                    chapter_id=chapter_id,
                    name=entity.name,
                    kind=entity.kind,
                    description=entity.description,
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
