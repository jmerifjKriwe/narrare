"""HTTP surface. Parses, delegates to the service, returns; no logic here."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.knowledge.schemas import (
    AcceptRead,
    ConsistencyAccepted,
    DocumentRead,
    EntityMerge,
    EntityRead,
    EntityUpdate,
    ExtractionAccepted,
    ExtractionRequest,
    FindingRead,
    ReembedResult,
    RelationCreate,
    RelationPatch,
    RelationRead,
    SearchHit,
    SearchRequest,
    SkippedRelationRead,
    SuggestionRead,
)
from app.capabilities.knowledge.service import (
    AlreadyReviewedError,
    CrossNovelMergeError,
    DocumentTooLargeError,
    EmptyDocumentError,
    FindingAlreadyReviewedError,
    InvalidEntityUpdateError,
    InvalidRelationError,
    KnowledgeService,
    NotFoundError,
    RelationExistsError,
    SelfMergeError,
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


@router.post("/extraction/{novel_id}", response_model=ExtractionAccepted, status_code=202)
async def start_extraction(
    novel_id: UUID, payload: ExtractionRequest, service: ServiceDep
) -> ExtractionAccepted:
    """Enqueue entity extraction for a chapter. The worker does the rest; poll
    ``GET /api/jobs/{job_id}`` — the row's state is the answer.

    Respond with HTTP 404 for an absent or unowned novel or chapter, including
    a chapter from a different novel, or HTTP 409 when setup is required.
    """
    try:
        job = await service.enqueue_extraction(novel_id, payload.chapter_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel or chapter not found") from None
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None
    return ExtractionAccepted(job_id=job.id)


@router.get("/novels/{novel_id}/entities", response_model=list[EntityRead])
async def list_entities(
    novel_id: UUID,
    service: ServiceDep,
    type: str | None = None,
    tag: str | None = None,
    q: str | None = None,
) -> list[EntityRead]:
    """The novel's entities: filtered by type and tag, or fuzzy-found by q
    (the trigram tier); unfiltered, oldest first.

    Raise HTTP 404 for an absent or unowned novel.
    """
    try:
        entities = await service.list_entities(novel_id, type=type, tag=tag, q=q)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None
    return [EntityRead.model_validate(entity) for entity in entities]


@router.get("/novels/{novel_id}/suggestions", response_model=list[SuggestionRead])
async def list_suggestions(
    novel_id: UUID,
    service: ServiceDep,
    status: Literal["pending", "accepted", "discarded"] = "pending",
) -> list[SuggestionRead]:
    """The novel's suggestions in one review state; pending is the queue.

    Return them oldest first; raise HTTP 404 for an absent or unowned novel.
    """
    try:
        suggestions = await service.list_suggestions(novel_id, status)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None
    return [SuggestionRead.model_validate(suggestion) for suggestion in suggestions]


@router.post("/suggestions/{suggestion_id}/accept", response_model=AcceptRead)
async def accept_suggestion(suggestion_id: UUID, service: ServiceDep) -> AcceptRead:
    """Accept: the entity is created, its proposed relations placed, and the
    suggestion consumed, once.

    Return the entity and the proposals that could not be placed — a target
    still pending, absent, or ambiguous (D8); the UI announces them once,
    and no ledger keeps them. Raise HTTP 404 for an absent or unowned
    suggestion, or HTTP 409 for an already reviewed suggestion.
    """
    try:
        entity, skipped = await service.accept_suggestion(suggestion_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="suggestion not found") from None
    except AlreadyReviewedError:
        raise HTTPException(status_code=409, detail="suggestion already reviewed") from None
    except EmbeddingMismatchError as error:
        # Birth embeds (D5); a model that answers at another width than the
        # entity corpus is the upload's refusal, same code, same fix.
        raise HTTPException(
            status_code=409,
            detail={"code": "embedding-mismatch", "stored": error.stored, "found": error.found},
        ) from None
    return AcceptRead(
        entity=EntityRead.model_validate(entity),
        skipped_relations=[
            SkippedRelationRead(target_name=skip.target_name, relation_type=skip.relation_type)
            for skip in skipped
        ],
    )


@router.post("/suggestions/{suggestion_id}/discard", response_model=SuggestionRead)
async def discard_suggestion(suggestion_id: UUID, service: ServiceDep) -> SuggestionRead:
    """Discard: the suggestion is consumed without creating anything.

    Return the suggestion; raise HTTP 404 for an absent or unowned suggestion,
    or HTTP 409 for an already reviewed suggestion.
    """
    try:
        suggestion = await service.discard_suggestion(suggestion_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="suggestion not found") from None
    except AlreadyReviewedError:
        raise HTTPException(status_code=409, detail="suggestion already reviewed") from None
    return SuggestionRead.model_validate(suggestion)


@router.post("/consistency/{novel_id}", response_model=ConsistencyAccepted, status_code=202)
async def start_consistency(novel_id: UUID, service: ServiceDep) -> ConsistencyAccepted:
    """Enqueue the whole-novel consistency check. The worker does the rest;
    poll ``GET /api/jobs/{job_id}`` — the row's state is the answer.

    Raise HTTP 404 for an absent or unowned novel, or HTTP 409 if setup is required.
    """
    try:
        job = await service.enqueue_consistency(novel_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None
    return ConsistencyAccepted(job_id=job.id)


@router.get("/novels/{novel_id}/findings", response_model=list[FindingRead])
async def list_findings(
    novel_id: UUID,
    service: ServiceDep,
    status: Literal["pending", "acknowledged", "dismissed"] = "pending",
) -> list[FindingRead]:
    """The novel's findings in one review state; pending is the queue.

    Return them oldest first; raise HTTP 404 for an absent or unowned novel.
    """
    try:
        findings = await service.list_findings(novel_id, status)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None
    return [FindingRead.model_validate(finding) for finding in findings]


@router.post("/findings/{finding_id}/acknowledge", response_model=FindingRead)
async def acknowledge_finding(finding_id: UUID, service: ServiceDep) -> FindingRead:
    """Acknowledge: the finding is consumed — seen, the text stays as it is.

    Return the finding; raise HTTP 404 for an absent or unowned finding,
    or HTTP 409 for an already reviewed finding.
    """
    try:
        finding = await service.acknowledge_finding(finding_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="finding not found") from None
    except FindingAlreadyReviewedError:
        raise HTTPException(status_code=409, detail="finding already reviewed") from None
    return FindingRead.model_validate(finding)


@router.post("/findings/{finding_id}/dismiss", response_model=FindingRead)
async def dismiss_finding(finding_id: UUID, service: ServiceDep) -> FindingRead:
    """Dismiss a finding and return its retained row with status dismissed.

    Raise HTTP 404 for an absent or unowned finding, or HTTP 409 if already reviewed.
    """
    try:
        finding = await service.dismiss_finding(finding_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="finding not found") from None
    except FindingAlreadyReviewedError:
        raise HTTPException(status_code=409, detail="finding already reviewed") from None
    return FindingRead.model_validate(finding)


@router.patch("/entities/{entity_id}", response_model=EntityRead)
async def update_entity(entity_id: UUID, payload: EntityUpdate, service: ServiceDep) -> EntityRead:
    """Correct an entity by hand: only the fields the body carries change.

    Return the entity; raise HTTP 404 for an absent or unowned entity,
    HTTP 422 for an invalid name, type, alias or tag — a null content
    clears the body — or HTTP 409 when the configured embedding model
    answers at another width than the entity corpus was embedded at.
    """
    try:
        entity = await service.update_entity(entity_id, payload)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="entity not found") from None
    except InvalidEntityUpdateError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except EmbeddingMismatchError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "embedding-mismatch", "stored": error.stored, "found": error.found},
        ) from None
    return EntityRead.model_validate(entity)


@router.delete("/entities/{entity_id}", status_code=204)
async def delete_entity(entity_id: UUID, service: ServiceDep) -> None:
    """Delete an entity. Its relations' foreign keys cascade: the edges go
    with the row.

    Raise HTTP 404 for an absent or unowned entity.
    """
    try:
        await service.delete_entity(entity_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="entity not found") from None


@router.get("/entities/{entity_id}/relations", response_model=list[RelationRead])
async def list_relations(entity_id: UUID, service: ServiceDep) -> list[RelationRead]:
    """The entity's relations, both directions, oldest first.

    Raise HTTP 404 for an absent or unowned entity — another user's rows
    are the same absence, including their edges.
    """
    try:
        relations = await service.entity_relations(entity_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="entity not found") from None
    return [RelationRead.model_validate(relation) for relation in relations]


@router.post("/entities/{entity_id}/relations", response_model=RelationRead, status_code=201)
async def add_relation(
    entity_id: UUID, payload: RelationCreate, service: ServiceDep
) -> RelationRead:
    """Create a directed edge to another entity of the same novel.

    Self-relations are allowed. Raise HTTP 404 when either end is absent
    or unowned or not of this novel, HTTP 422 for a blank or over-long
    type, or HTTP 409 when this exact edge carries the type already.
    """
    try:
        relation = await service.add_relation(
            entity_id, payload.to_entity_id, payload.relation_type, payload.note
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="entity not found") from None
    except InvalidRelationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except RelationExistsError:
        raise HTTPException(status_code=409, detail="this relation exists already") from None
    return RelationRead.model_validate(relation)


@router.patch("/relations/{relation_id}", response_model=RelationRead)
async def update_relation(
    relation_id: UUID, payload: RelationPatch, service: ServiceDep
) -> RelationRead:
    """Retype or re-note an edge; the ends are immutable.

    Return the edge; raise HTTP 404 for an absent or unowned edge,
    HTTP 422 for a blank or over-long type, or HTTP 409 when the new type
    would duplicate the edge's sibling.
    """
    try:
        relation = await service.update_relation(relation_id, payload)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="relation not found") from None
    except InvalidRelationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except RelationExistsError:
        raise HTTPException(status_code=409, detail="this relation exists already") from None
    return RelationRead.model_validate(relation)


@router.delete("/relations/{relation_id}", status_code=204)
async def delete_relation(relation_id: UUID, service: ServiceDep) -> None:
    """Delete one edge: exactly the edge.

    Raise HTTP 404 for an absent or unowned edge.
    """
    try:
        await service.delete_relation(relation_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="relation not found") from None


@router.post("/entities/{entity_id}/merge", response_model=EntityRead)
async def merge_entity(entity_id: UUID, payload: EntityMerge, service: ServiceDep) -> EntityRead:
    """Fold this entity into another: the target survives, the source is
    deleted, and the source's edges re-point and its fields fold into the
    survivor.

    Return the folded target; raise HTTP 404 if either entity is absent or
    unowned, HTTP 422 for a self-merge or a target in another novel, or
    HTTP 409 when the configured embedding model answers at another width
    than the entity corpus was embedded at.
    """
    try:
        target = await service.merge_entities(entity_id, payload.target_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="entity not found") from None
    except SelfMergeError:
        raise HTTPException(status_code=422, detail="an entity cannot merge into itself") from None
    except CrossNovelMergeError:
        raise HTTPException(
            status_code=422, detail="an entity cannot merge into another novel's entity"
        ) from None
    except EmbeddingMismatchError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "embedding-mismatch", "stored": error.stored, "found": error.found},
        ) from None
    return EntityRead.model_validate(target)
