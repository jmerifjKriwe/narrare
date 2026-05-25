"""KB extraction routes — entity extraction from chapter text.

Thin delegation to ExtractionService (RULE-06). No business logic here.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException

from narrare._app.dependencies import CurrentUserIdDep
from narrare.kb.dependencies import get_extraction_service
from narrare.kb.extraction_service import ExtractionService
from narrare.kb.schemas_extraction import ApplyExtractionRequest, ApplyExtractionResponse

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["kb-extraction"])


@router.post("/novels/{novel_id}/kb/extract/{chapter_id}")
async def extract_chapter(
    novel_id: UUID,
    chapter_id: UUID,
    user_id: CurrentUserIdDep,
    service: ExtractionService = Depends(get_extraction_service),
) -> dict[str, object]:
    """Extract entities, facts, and relationships from a chapter into the KB.

    Analyzes chapter text and extracts structured data:
    - New entities (characters, locations, factions, concepts, objects, systems)
    - Existing entity updates (new information about known entities)
    - Relationships between entities
    - Conflicts with existing KB data

    Returns ExtractionOutput with results and analysis notes.
    """
    try:
        result = await service.extract_from_chapter(
            novel_id=novel_id,
            chapter_id=chapter_id,
            user_id=UUID(user_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("extraction_failed", chapter_id=str(chapter_id), error=str(exc))
        raise HTTPException(status_code=500, detail="Extraction failed") from exc

    return {
        "results": [item.model_dump(mode="json") for item in result.results],
        "analysis_notes": result.analysis_notes,
    }


@router.post("/novels/{novel_id}/kb/extract/apply")
async def apply_extraction(
    novel_id: UUID,
    body: ApplyExtractionRequest,
    user_id: CurrentUserIdDep,
    service: ExtractionService = Depends(get_extraction_service),
) -> ApplyExtractionResponse:
    """Apply endorsed extraction items to the Knowledge Base.

    Creates new entities, updates existing ones, and creates relationships
    based on the user's endorsement of extraction results.
    """
    try:
        result = await service.apply_extraction(
            novel_id=novel_id,
            user_id=UUID(user_id),
            items=body.items,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("apply_extraction_failed", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="Apply extraction failed") from exc
