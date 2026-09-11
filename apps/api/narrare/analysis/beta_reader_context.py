"""Beta reader context assembly — deps preparation + AnalysisError boundary.

Extracted from ``beta_reader_service.py`` (RULE-04 split): the service is a
thin orchestrator over sibling modules (cache / mapper / prompt /
agent_run); the deps-preparation and assembler error-mapping logic now
lives here too.

Ownership (IDOR remediation S12a): the assembler's Step 0 ownership gate
raises ``NotFoundError`` (foreign ≡ unknown → 404). That error is re-raised
UNWRAPPED — it must never be masked by the generic ``AnalysisError`` wrap
(RULE-11: an authorization decision is not an internal failure). Any other
assembler failure maps to :class:`AnalysisError` (logged, never swallowed).
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare.analysis.errors import AnalysisError, CacheRetrievalError
from narrare.analysis.schemas import BetaReaderResponse
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from narrare.analysis.beta_reader_cache import BetaReaderCache
    from narrare.analysis.context_assembler import ContextAssembler
    from narrare_core.agents.beta_reader_types import BetaReaderDeps

logger = structlog.get_logger(__name__)


async def assemble_context(
    assembler: ContextAssembler,
    novel_id: UUID,
    user_id: UUID,
    chapter_ids: list[str],
) -> BetaReaderDeps:
    """Assemble BetaReaderDeps from database.

    Raises:
        NotFoundError: Ownership gate failure — propagated UNWRAPPED so the
            global handler maps it to 404 (IDOR S12a; RULE-11: the generic
            wrap must never mask an authorization decision).
        AnalysisError: If context assembly fails.
    """
    try:
        return await assembler.build_context(
            novel_id=novel_id,
            chapter_ids=[UUID(cid) for cid in chapter_ids],
            user_id=user_id,
        )
    except NotFoundError:
        raise
    except Exception as exc:
        logger.error(
            "context_assembly_failed",
            novel_id=str(novel_id),
            error=str(exc),
        )
        raise AnalysisError("Failed to assemble analysis context") from exc


async def deep_dive_deps(
    assembler: ContextAssembler,
    cache: BetaReaderCache,
    *,
    novel_id: UUID,
    user_id: UUID,
    chapter_ids: list[str],
    category_value: str,
) -> BetaReaderDeps:
    """Assemble deep-dive deps: chapter context + Phase 1 summary enrichment.

    Assembles the chapter context first (needed to compute the content_hash
    for the Phase 1 lookup), retrieves the cached Phase 1 analysis via the
    content-aware key (ADR-021), and enriches the deps with the deep-dive
    category plus the Phase 1 strengths / feedback summaries.

    Raises:
        NotFoundError: Ownership gate failure — propagated UNWRAPPED (see
            :func:`assemble_context`).
        CacheRetrievalError: If the Phase 1 analysis is not cached.
        AnalysisError: If context assembly fails.
    """
    # 1. Assemble context first (needed to compute content_hash for Phase 1 lookup)
    deps = await assemble_context(assembler, novel_id, user_id, chapter_ids)
    content_hash = hashlib.sha256(deps.chapter_text.encode()).hexdigest()[:12]

    # 2. Retrieve Phase 1 from cache for context (using content-aware key)
    phase1_json = await cache.get(str(novel_id), chapter_ids, content_hash=content_hash)
    if phase1_json is None:
        raise CacheRetrievalError("Phase 1 analysis not found. Run full analysis first.")

    phase1 = BetaReaderResponse.model_validate_json(phase1_json)
    deps.deepdive_category = category_value
    deps.phase1_strengths_summary = "; ".join(s.title for s in phase1.strengths)
    deps.phase1_feedback_summary = "; ".join(f.title for f in phase1.feedback[:10])
    return deps
