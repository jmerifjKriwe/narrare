"""REST endpoint for chapter summarization.

Thin delegation layer (RULE-06): every route immediately delegates to
ChapterSummaryService. No business logic lives here.
"""

from __future__ import annotations

from uuid import UUID  # noqa: TC003 — needed at runtime for FastAPI route params

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from narrare.writing.summary_contracts import SummaryResult
from narrare.writing.summary_deps import get_summary_service
from narrare_core.shared.errors import NotFoundError, WritingError


class SummarizeRequest(BaseModel):
    """Request body for chapter summarization."""

    max_sentences: int = Field(default=4, ge=1, le=20, description="Max sentences in summary")
    language: str = Field(default="en", max_length=10, description="Output language code")


router = APIRouter(prefix="/summary", tags=["summary"])


@router.post("/chapters/{chapter_id}", response_model=SummaryResult)
async def summarize_chapter(
    chapter_id: UUID,
    request: SummarizeRequest | None = None,
    service=Depends(get_summary_service),
) -> SummaryResult:
    """Generate a summary for the given chapter.

    Args:
        chapter_id: UUID of the chapter to summarize.
        request: Optional request body with max_sentences and language.
        service: Injected ChapterSummaryService instance.

    Returns:
        SummaryResult with summary text, word count, and key points.

    Raises:
        404: If the chapter does not exist.
        500: If the LLM call fails.
    """
    max_sentences = request.max_sentences if request is not None else 4
    language = request.language if request is not None else "en"

    try:
        result = await service.summarize(
            chapter_id=chapter_id,
            max_sentences=max_sentences,
            language=language,
        )
        return result
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WritingError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
