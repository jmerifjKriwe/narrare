"""KB merge routes — thin delegation to KBMergeService (RULE-06).

POST /novels/{novel_id}/kb/merge — analyze candidate pairs for merging.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from narrare._app.dependencies import (
    CurrentUserIdDep,
    SessionDep,
    get_model_registry,
    get_model_routing_resolver,
)
from narrare.kb.merge_service import KBMergeService
from narrare.kb.schemas_merge import MergeRequest, MergeResponse
from narrare.novels.repository import NovelRepository
from narrare_core.shared.errors import NotFoundError

router = APIRouter(tags=["kb"])


@router.post(
    "/novels/{novel_id}/kb/merge",
    response_model=MergeResponse,
)
async def analyze_merge_candidates(
    novel_id: uuid.UUID,
    request: MergeRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> MergeResponse:
    """Analyze candidate pairs for KB entity merging.

    Evaluates whether entity pairs should be merged, kept distinct,
    or flagged as uncertain for human review.
    """
    from narrare_core.llm.intents import LLMIntent

    uid = uuid.UUID(user_id)
    nid = novel_id

    # Validate novel exists
    novel_repo = NovelRepository(session)
    novel = await novel_repo.get_by_id(nid, uid)
    if novel is None:
        raise NotFoundError("Novel", identifier=str(nid))

    # Resolve model config
    registry = get_model_registry()
    resolver = get_model_routing_resolver(session)
    resolved = await resolver.resolve(LLMIntent.KB_CONSISTENCY, uid, nid)

    service = KBMergeService(
        novel_repo=novel_repo,
        model_registry=registry,
        model_config=resolved.config,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
    )
    return await service.analyze_merge_candidates(nid, uid, request)
