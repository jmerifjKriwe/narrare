"""REST endpoint for chapter summarization.

Thin delegation layer (RULE-06): every route immediately delegates to
ChapterSummaryService. No business logic lives here.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from narrare._app.dependencies_auth import CurrentUserIdDep
from narrare.writing.summary_contracts import SummaryResult
from narrare.writing.summary_deps import get_summary_service
from narrare_core.shared.errors import WritingError


class SummarizeRequest(BaseModel):
    """Request body for chapter summarization."""

    max_sentences: int = Field(default=4, ge=1, le=20, description="Max sentences in summary")
    language: str = Field(default="en", max_length=10, description="Output language code")


router = APIRouter(prefix="/summary", tags=["summary"])


@router.post("/chapters/{chapter_id}", response_model=SummaryResult)
async def summarize_chapter(
    chapter_id: UUID,
    user_id: CurrentUserIdDep,
    request: SummarizeRequest | None = None,
    service=Depends(get_summary_service),
) -> SummaryResult:
    """Generate a summary for the given chapter.

    Args:
        chapter_id: UUID of the chapter to summarize.
        user_id: Authenticated user identifier (ownership check).
        request: Optional request body with max_sentences and language.
        service: Injected ChapterSummaryService instance.

    Returns:
        SummaryResult with summary text, word count, and key points.

    Raises:
        404: If the chapter does not exist or belongs to another user.
        500: If the LLM call fails.
    """
    max_sentences = request.max_sentences if request is not None else 4
    language = request.language if request is not None else "en"

    try:
        result = await service.summarize(
            chapter_id=chapter_id,
            max_sentences=max_sentences,
            language=language,
            user_id=user_id,
        )
        return result
    except WritingError as exc:
        # NotFoundError deliberately propagates to the global NarrareError
        # handler (404 with `code` in the body — consistent error shape).
        # WritingError stays a manual conversion: it is a plain NarrareError
        # the global handler would map to its 400 default, so the 500 status
        # for LLM failures depends on this clause.
        raise HTTPException(status_code=500, detail=str(exc)) from exc
