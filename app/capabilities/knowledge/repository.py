"""Document and chunk persistence. Both scoped to one user."""

from collections.abc import Sequence  # noqa: TC003
from uuid import UUID  # noqa: TC003

from app.kernel.contracts.models import Chunk, Document
from app.kernel.db.base import ScopedRepository


class DocumentRepository(ScopedRepository[Document]):
    model = Document

    async def list(self) -> Sequence[Document]:
        result = await self.session.scalars(self.query().order_by(Document.created_at.desc()))
        return result.all()

    async def create(self, title: str) -> Document:
        document = Document(user_id=self.user_id, title=title)
        self.session.add(document)
        await self.session.flush()
        return document


class ChunkRepository(ScopedRepository[Chunk]):
    model = Chunk

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

    async def search(
        self, vector: Sequence[float], limit: int
    ) -> Sequence[tuple[Chunk, str, float]]:
        """Nearest chunks by cosine distance, with their document title.

        The ordering happens in the database, where the vector lives; this method
        only names the distance once so the score cannot drift from the order.
        """
        distance = Chunk.embedding.cosine_distance(list(vector)).label("distance")
        statement = (
            self.query()
            .add_columns(Document.title, distance)
            .join(Document, Document.id == Chunk.document_id)
            .order_by(distance)
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return [(chunk, title, 1.0 - score) for chunk, title, score in result.all()]
