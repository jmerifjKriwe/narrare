"""HTTP surface. Parses, delegates to the service, returns; no logic here."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.knowledge.schemas import (
    DocumentRead,
    ReembedResult,
    SearchHit,
    SearchRequest,
)
from app.capabilities.knowledge.service import (
    DocumentTooLargeError,
    EmptyDocumentError,
    KnowledgeService,
)
from app.kernel.auth import SetupRequiredError, current_user_id
from app.kernel.db.session import get_session
from app.kernel.embeddings import EmbeddingProvider, get_embedding_provider
from app.kernel.retrieval import EmbeddingMismatchError

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
    except DocumentTooLargeError:
        raise HTTPException(status_code=413, detail="document too large") from None
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None
    except EmbeddingMismatchError as error:
        # A dict, not a sentence: the UI localizes this error and needs a code.
        raise HTTPException(
            status_code=409,
            detail={"code": "embedding-mismatch", "stored": error.stored, "found": error.found},
        ) from None
    return DocumentRead.model_validate(document)


@router.post("/reembed", response_model=ReembedResult)
async def reembed(service: ServiceDep) -> ReembedResult:
    """Re-embed the corpus through the configured model: the mismatch fix."""
    try:
        return await service.reembed()
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None


@router.post("/search", response_model=list[SearchHit])
async def search(payload: SearchRequest, service: ServiceDep) -> list[SearchHit]:
    try:
        hits = await service.search(payload.query, payload.limit)
    except EmbeddingMismatchError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "embedding-mismatch", "stored": error.stored, "found": error.found},
        ) from None
    return [
        SearchHit(
            chunk_id=hit.chunk_id,
            document_id=hit.document_id,
            document_title=hit.document_title,
            text=hit.text,
            score=hit.score,
        )
        for hit in hits
    ]
