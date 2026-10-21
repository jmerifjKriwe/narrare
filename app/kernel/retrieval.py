"""Passage retrieval: the query knowledge writes and chat reads.

One implementation, in the kernel, because two capabilities need it and may not
import each other (D13). The user scope comes from the repository base, so the
kernel query is as narrow as any capability-owned one.

The width guard lives here too, because it is the one rule that makes a mixed
schema safe: vectors from two embedding models are not comparable, so a corpus
stays at the width it was embedded at, and a model switch is a refusal that
names the fix instead of silently degraded search results.
"""

from collections.abc import Sequence  # noqa: TC003
from dataclasses import dataclass
from uuid import UUID  # noqa: TC003

from sqlalchemy import select

from app.kernel.contracts.models import Chunk, Document
from app.kernel.db.base import ScopedRepository


class EmbeddingMismatchError(Exception):
    """The configured model answers at another width than the stored corpus."""

    def __init__(self, stored: int, found: int) -> None:
        self.stored = stored
        self.found = found
        super().__init__(
            f"the knowledge base was embedded at width {stored},"
            f" the configured model answers at {found}; re-upload its documents"
        )


@dataclass(frozen=True)
class Passage:
    """A retrieved chunk with the document it belongs to and its score."""

    chunk_id: UUID
    document_id: UUID
    document_title: str
    text: str
    score: float


class PassageRepository(ScopedRepository[Chunk]):
    model = Chunk

    async def stored_width(self) -> int | None:
        """The width the user's corpus was embedded at; None when it is empty."""
        result = await self.session.scalars(
            select(Document.embedding_width)
            .where(Document.user_id == self.user_id)
            .order_by(Document.created_at)
            .limit(1)
        )
        widths = result.all()
        return widths[0] if widths else None

    async def search(self, vector: Sequence[float], limit: int) -> list[Passage]:
        """Nearest passages by cosine distance, scoped to the requesting user.

        The ordering happens in the database, where the vector lives; this method
        names the distance once so the score cannot drift from the order.
        """
        stored = await self.stored_width()
        if stored is not None and stored != len(vector):
            raise EmbeddingMismatchError(stored, len(vector))
        distance = Chunk.embedding.cosine_distance(list(vector)).label("distance")
        statement = (
            self.query()
            .add_columns(Document.title, distance)
            .join(Document, Document.id == Chunk.document_id)
            .order_by(distance)
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return [
            Passage(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_title=title,
                text=chunk.text,
                score=1.0 - score,
            )
            for chunk, title, score in result.all()
        ]
