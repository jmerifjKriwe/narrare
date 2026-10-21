"""Passage retrieval: the query knowledge writes and chat reads.

One implementation, in the kernel, because two capabilities need it and may not
import each other (D13). The user scope comes from the repository base, so the
kernel query is as narrow as any capability-owned one.
"""

from collections.abc import Sequence  # noqa: TC003
from dataclasses import dataclass
from uuid import UUID  # noqa: TC003

from app.kernel.contracts.models import Chunk, Document
from app.kernel.db.base import ScopedRepository


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

    async def search(self, vector: Sequence[float], limit: int) -> list[Passage]:
        """Nearest passages by cosine distance, scoped to the requesting user.

        The ordering happens in the database, where the vector lives; this method
        names the distance once so the score cannot drift from the order.
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
