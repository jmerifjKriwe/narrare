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
