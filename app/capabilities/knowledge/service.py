"""Knowledge logic: ingest a text, search it. The router only translates."""

from collections.abc import Sequence  # noqa: TC003
from uuid import UUID  # noqa: TC003

from app.capabilities.knowledge.chunking import chunk_text
from app.capabilities.knowledge.repository import ChunkRepository, DocumentRepository
from app.kernel.contracts.models import Chunk, Document  # noqa: TC002
from app.kernel.embeddings import EmbeddingProvider  # noqa: TC002
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002


class EmptyDocumentError(Exception):
    """The upload carries no text to embed."""


class KnowledgeService:
    def __init__(self, session: AsyncSession, user_id: UUID, embeddings: EmbeddingProvider) -> None:
        self.session = session
        self.embeddings = embeddings
        self.documents = DocumentRepository(session, user_id)
        self.chunks = ChunkRepository(session, user_id)

    async def list_documents(self) -> Sequence[Document]:
        return await self.documents.list()

    async def ingest(self, title: str, text: str) -> Document:
        chunks = chunk_text(text)
        if not chunks:
            raise EmptyDocumentError
        vectors = await self.embeddings.embed(chunks)
        document = await self.documents.create(title)
        await self.chunks.create_many(document.id, chunks, vectors)
        await self.session.commit()
        return document

    async def search(self, query: str, limit: int) -> Sequence[tuple[Chunk, str, float]]:
        [vector] = await self.embeddings.embed([query])
        return await self.chunks.search(vector, limit)
