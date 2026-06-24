"""PROMPT-003 (CR-AUFG-07-16) thin routes: preview, reset, optional SSE live test.

Split from ``router.py`` for RULE-04 (router hard limit 150 lines).
Service factories live in ``deps.py`` (same split pattern as
``writing/deps.py``). Routes use ``{prompt_id:path}`` and are registered
in ``main.py`` alongside the existing prompts tree. POST routes do not
conflict with the existing GET/PUT/DELETE ``/{prompt_id:path}`` routes
in ``router.py`` because HTTP methods differ.

RULE-21 deviation: endpoints live under ``/api/v1/prompts/...`` (not
``/api/v1/settings/prompts/{intent}/...`` as spec prose suggests).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare._app.rate_limits import AI_PROMPT_LIVE_TEST_LIMITER
from narrare.prompts.deps import (
    get_live_test_service,
    get_preview_service,
    get_reset_service,
)
from narrare.prompts.schemas_prompt_ux import (
    LiveTestRequest,
    PreviewRequest,
    PreviewResponse,
    ResetResponse,
)
from narrare_core.shared.errors import ConfigurationError, ValidationError

if TYPE_CHECKING:
    from narrare.prompts.live_test_service import PromptLiveTestApiService
    from narrare.prompts.preview_service import (
        PromptPreviewApiService,
        PromptResetApiService,
    )

router = APIRouter(prefix="/prompts", tags=["prompts"])


@router.post(
    "/{prompt_id:path}/preview",
    response_model=PreviewResponse,
)
async def preview_prompt(
    prompt_id: str,
    request: PreviewRequest,
    user_id: CurrentUserIdDep,
    service: PromptPreviewApiService = Depends(get_preview_service),
) -> PreviewResponse:
    """Provider-free preview — no LLM, no tokens, no provider secret required."""
    return await service.preview(prompt_id, request)


@router.post(
    "/{prompt_id:path}/reset",
    response_model=ResetResponse,
)
async def reset_prompt(
    prompt_id: str,
    user_id: CurrentUserIdDep,
    service: PromptResetApiService = Depends(get_reset_service),
) -> ResetResponse:
    """Reset the override for one prompt and return effective metadata."""
    return await service.reset_with_metadata(prompt_id)


@router.post(
    "/{prompt_id:path}/live-test",
    dependencies=[Depends(AI_PROMPT_LIVE_TEST_LIMITER)],
)
async def start_live_test(
    prompt_id: str,
    request: LiveTestRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StreamingResponse:
    """Optional SSE live test — provider-/secret-gated, rate-limited.

    Validates first (so 400/503 returns before SSE starts), then returns
    a ``StreamingResponse`` of ``text/event-stream`` frames.

    Error mapping:
        - ``acknowledge_token_cost=False`` → 400 (Bad Request).
        - No provider configured → 503 (Service Unavailable).
        - Rate limit exceeded → 429 (from the limiter dependency).
    """
    service: PromptLiveTestApiService = await get_live_test_service(session)

    try:
        metadata = await service.validate_live_test(prompt_id, request, user_id=user_id)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return StreamingResponse(
        service.stream_live_test(prompt_id, request, user_id=user_id, metadata=metadata),
        media_type="text/event-stream",
    )
