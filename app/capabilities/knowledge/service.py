"""Knowledge logic: ingest a text, search it. The router only translates."""

from collections.abc import Sequence  # noqa: TC003
from uuid import UUID  # noqa: TC003

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.capabilities.knowledge.chunking import chunk_text
from app.capabilities.knowledge.repository import ChunkRepository, DocumentRepository
from app.capabilities.knowledge.schemas import ReembedResult
from app.kernel.auth import SetupRequiredError
from app.kernel.contracts.models import Document, User
from app.kernel.embeddings import EmbeddingProvider  # noqa: TC001
from app.kernel.retrieval import EmbeddingMismatchError, Passage, PassageRepository

MAX_UPLOAD_BYTES = 1_000_000
"""One document, at most. Ingestion embeds in-request; an unbounded upload would
hold the worker and, with a paid provider, bill without limit."""


class EmptyDocumentError(Exception):
    """The upload carries no text to embed."""


class DocumentTooLargeError(Exception):
    """The upload is larger than MAX_UPLOAD_BYTES."""


class KnowledgeService:
    def __init__(self, session: AsyncSession, user_id: UUID, embeddings: EmbeddingProvider) -> None:
        self.session = session
        self.user_id = user_id
        self.embeddings = embeddings
        self.documents = DocumentRepository(session, user_id)
        self.chunks = ChunkRepository(session, user_id)
        self.passages = PassageRepository(session, user_id)

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
