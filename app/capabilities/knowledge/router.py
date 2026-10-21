"""HTTP surface. Parses, delegates to the service, returns; no logic here."""

from typing import Annotated
from uuid import UUID

from app.capabilities.knowledge.schemas import DocumentRead, SearchHit, SearchRequest
from app.capabilities.knowledge.service import EmptyDocumentError, KnowledgeService
from app.kernel.auth import current_user_id
from app.kernel.db.session import get_session
from app.kernel.embeddings import EmbeddingProvider, get_embedding_provider
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UUID, Depends(current_user_id)]
EmbeddingsDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]


def _service(session: SessionDep, user_id: UserDep, embeddings: EmbeddingsDep) -> KnowledgeService:
    return KnowledgeService(session, user_id, embeddings)


ServiceDep = Annotated[KnowledgeService, Depends(_service)]


@router.get("/documents", response_model=list[DocumentRead])
async def list_documents(service: ServiceDep) -> list[DocumentRead]:
    return [DocumentRead.model_validate(document) for document in await service.list_documents()]


@router.post("/documents", response_model=DocumentRead, status_code=201)
async def upload_document(
    service: ServiceDep,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
) -> DocumentRead:
    """Ingest a text file. Plain text only; the body is decoded as UTF-8."""
    text = (await file.read()).decode("utf-8", errors="replace")
    resolved = (title or "").strip() or file.filename
    if not resolved:
        raise HTTPException(status_code=422, detail="document needs a title or a filename")
    try:
        document = await service.ingest(resolved, text)
    except EmptyDocumentError:
        raise HTTPException(status_code=422, detail="document is empty") from None
    return DocumentRead.model_validate(document)


@router.post("/search", response_model=list[SearchHit])
async def search(payload: SearchRequest, service: ServiceDep) -> list[SearchHit]:
    hits = await service.search(payload.query, payload.limit)
    return [
        SearchHit(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_title=title,
            text=chunk.text,
            score=score,
        )
        for chunk, title, score in hits
    ]
