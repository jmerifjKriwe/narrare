"""Corpus pass routes — honest estimate + start (F3, spec §4.3/§4.4).

A separate module from ``router_extraction_batch.py`` (RULE-04: that file
is at 115/150 router lines and the two corpus routes would breach the
150-line hard limit — the prescribed response is one router file per
resource sub-group). Routes delegate to the SAME
:class:`BulkExtractionService` factory, so the batch suite's dispatcher
override covers these endpoints identically in tests.

Error translation lives in the global ``NarrareError`` handler
(``_app/main.py``): ``NotFoundError`` → 404 (foreign novel), 409 for the
engine's single-active-job rule, ``ValidationError`` → 422 with honest
counts (empty prefix / oversized first chapter) — this router carries no
try/except (RULE-06).

NO ``AI_ANALYSIS_LIMITER`` dependency: no LLM call happens in-request —
the estimate is arithmetic and the run is paced by the background runner
against the shared analysis budget (ADR-092 D7a).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from narrare._app.dependencies import CurrentUserIdDep
from narrare.kb.bulk_extraction.dependencies import get_bulk_extraction_service
from narrare.kb.bulk_extraction.schemas import BulkExtractionJobView
from narrare.kb.bulk_extraction.schemas_corpus import CorpusEstimateView
from narrare.kb.bulk_extraction.service import BulkExtractionService

router = APIRouter(tags=["kb-extraction"])


@router.get(
    "/novels/{novel_id}/kb/extract/bulk/corpus/estimate",
    response_model=CorpusEstimateView,
)
async def get_corpus_pass_estimate(
    novel_id: UUID,
    user_id: CurrentUserIdDep,
    service: BulkExtractionService = Depends(get_bulk_extraction_service),
) -> CorpusEstimateView:
    """Honest pre-run estimate over the novel's position-order prefix (§4.3).

    A zero-chapter novel yields the honest-0 estimate (200) — only START
    rejects emptiness with a 422.
    """
    return await service.corpus_estimate(novel_id, UUID(user_id))


@router.post(
    "/novels/{novel_id}/kb/extract/bulk/corpus",
    response_model=BulkExtractionJobView,
    status_code=status.HTTP_201_CREATED,
)
async def start_corpus_pass(
    novel_id: UUID,
    user_id: CurrentUserIdDep,
    service: BulkExtractionService = Depends(get_bulk_extraction_service),
) -> BulkExtractionJobView:
    """Start a corpus pass over the START-time prefix (§4.4).

    Re-validates server-side (estimate drift → the new prefix, never a
    silent superset); 409 while another job is active for the novel; 422
    when no prefix fits. The runner is dispatched for the created job.
    """
    return await service.start_corpus(novel_id, UUID(user_id))
