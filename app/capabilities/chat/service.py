"""Chat logic: retrieve the passages, build the prompt. The router streams."""

from uuid import UUID  # noqa: TC003

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.capabilities.chat.prompts import CHAT_KEY, sources_block
from app.kernel.embeddings import EmbeddingProvider  # noqa: TC001
from app.kernel.prompts import render
from app.kernel.retrieval import Passage, PassageRepository


class ChatService:
    def __init__(self, session: AsyncSession, user_id: UUID, embeddings: EmbeddingProvider) -> None:
        self.session = session
        self.user_id = user_id
        self.embeddings = embeddings
        self.passages = PassageRepository(session, user_id)

    async def prepare(self, question: str, limit: int) -> tuple[str, list[Passage]]:
        """The prompt and the passages it cites.

        Read-only: chat writes nothing in the request path (D14). The returned
        passages are the sources the response carries. The prompt renders
        through the registry's effective chain — the user's global override,
        else the bundled template; chat has no novel scope. The sources ride
        pre-joined behind the kernel's marker (`sources_block`), and a render
        the chain refuses raises `PromptRenderError` — the router's error
        frame, never a silent bundled swap.
        """
        [vector] = await self.embeddings.embed([question])
        passages = await self.passages.search(vector, limit)
        prompt = await render(
            self.session,
            self.user_id,
            CHAT_KEY,
            {"question": question, "sources": sources_block(passages)},
        )
        return prompt, passages
