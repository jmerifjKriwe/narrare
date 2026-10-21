"""Chat logic: retrieve the passages, build the prompt. The router streams."""

from uuid import UUID  # noqa: TC003

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.capabilities.chat.prompts import chat_prompt
from app.kernel.embeddings import EmbeddingProvider  # noqa: RUF100, TC001, TC002
from app.kernel.retrieval import Passage, PassageRepository


class ChatService:
    def __init__(self, session: AsyncSession, user_id: UUID, embeddings: EmbeddingProvider) -> None:
        self.embeddings = embeddings
        self.passages = PassageRepository(session, user_id)

    async def prepare(self, question: str, limit: int) -> tuple[str, list[Passage]]:
        """The prompt and the passages it cites.

        Read-only: chat writes nothing in the request path (D14). The returned
        passages are the sources the response carries.
        """
        [vector] = await self.embeddings.embed([question])
        passages = await self.passages.search(vector, limit)
        return chat_prompt(question=question, passages=passages), passages
