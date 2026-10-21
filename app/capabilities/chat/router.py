"""HTTP surface. Parses, delegates to the service, streams; no logic here."""

import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from app.capabilities.chat.schemas import ChatRequest  # noqa: TC002
from app.capabilities.chat.service import ChatService
from app.kernel.auth import current_user_id
from app.kernel.db.session import get_session
from app.kernel.embeddings import EmbeddingProvider, get_embedding_provider
from app.kernel.llm import TextProvider, get_provider
from app.kernel.retrieval import Passage  # noqa: TC002
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/chat", tags=["chat"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UUID, Depends(current_user_id)]
EmbeddingsDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
ProviderDep = Annotated[TextProvider, Depends(get_provider)]


def _service(session: SessionDep, user_id: UserDep, embeddings: EmbeddingsDep) -> ChatService:
    return ChatService(session, user_id, embeddings)


ServiceDep = Annotated[ChatService, Depends(_service)]


async def _events(
    provider: TextProvider, prompt: str, passages: list[Passage]
) -> AsyncIterator[str]:
    """Sources first, then the answer, then done.

    The sources go out before the first token so the reader can show what the
    answer was built from while it is still arriving.
    """
    sources = [
        {
            "chunk_id": str(passage.chunk_id),
            "document_title": passage.document_title,
            "text": passage.text,
        }
        for passage in passages
    ]
    yield f"data: {json.dumps({'sources': sources})}\n\n"
    async for delta in provider.stream(prompt):
        yield f"data: {json.dumps({'delta': delta})}\n\n"
    yield "event: done\ndata: {}\n\n"


@router.post("/ask")
async def ask(
    payload: ChatRequest, service: ServiceDep, provider: ProviderDep
) -> StreamingResponse:
    prompt, passages = await service.prepare(payload.question, payload.limit)
    return StreamingResponse(_events(provider, prompt, passages), media_type="text/event-stream")
