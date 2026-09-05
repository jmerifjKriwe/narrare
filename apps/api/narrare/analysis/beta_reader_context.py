"""Beta reader context assembly — AnalysisError boundary for ``build_context``.

Extracted from ``beta_reader_service.py`` (RULE-04 split): the service is a
thin orchestrator over sibling modules (cache / mapper / prompt /
agent_run); the assembler error-mapping logic now lives here too.

Maps any assembler failure to :class:`AnalysisError` (RULE-11: logged,
never swallowed).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare.analysis.errors import AnalysisError

if TYPE_CHECKING:
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
        AnalysisError: If context assembly fails.
    """
    try:
        return await assembler.build_context(
            novel_id=novel_id,
            chapter_ids=[UUID(cid) for cid in chapter_ids],
            user_id=user_id,
        )
    except Exception as exc:
        logger.error(
            "context_assembly_failed",
            novel_id=str(novel_id),
            error=str(exc),
        )
        raise AnalysisError("Failed to assemble analysis context") from exc
