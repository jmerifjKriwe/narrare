"""Consistency service contracts — Protocol definitions.

Contracts are written before implementation (RULE-03).
Defines ``ConsistencyCheckerProtocol`` as the service-layer interface
for CONS-001 (Consistency Checker) and future CONS-002 (Custom Rules).

All domain enums and core types are imported from
``narrare_core.agents.consistency_types`` to avoid duplication.

See:
    :mod:`narrare.consistency.schemas` — Request/Response models.
    :mod:`narrare_core.agents.consistency_types` — Domain enums and core types.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.consistency.schemas import (
        ConsistencyRequest,
        ConsistencyResponse,
    )
    from narrare.consistency.stage_schemas import ConsistencyStageEvent
    from narrare_core.agents.consistency_types import ConsistencyDeps
    from narrare_core.agents.fact_extractor_types import TimelineEventEnvelope


@runtime_checkable
class ConsistencyCheckerProtocol(Protocol):
    """Protocol for consistency checking services.

    The service layer orchestrates:
    1. Access control (user has access to the novel).
    2. Chapter content collection (fetch requested chapter texts).
    3. KB entity summary assembly (build entity context from KB data).
    4. Agent invocation (call ConsistencyAgent with assembled data).
    5. Response mapping (map agent output to API response model).

    All clients (WebUI, MCP, A2A, CLI) call this same service interface.
    """

    async def check(
        self,
        *,
        novel_id: UUID,
        user_id: UUID,
        request: ConsistencyRequest,
    ) -> ConsistencyResponse:
        """Run consistency check on the requested scope.

        Cross-chapter and cross-entity consistency analysis. Compares
        facts extracted from chapter prose against KB entity data and
        across chapters. Returns issues grouped by severity and type.

        Args:
            novel_id: The novel to analyze.
            user_id: The user requesting analysis (for access control).
            request: Check parameters (check types, chapter scope, KB inclusion).

        Returns:
            Consistency response with issues grouped by severity and type,
            including error/warning/info counts and overall assessment.

        Raises:
            narrare_core.shared.errors.NotFoundError: If novel or chapters
                do not exist.
            narrare_core.shared.errors.ForbiddenError: If user does not
                have access to the novel.
        """
        ...

    async def check_chapter(
        self,
        *,
        novel_id: UUID,
        chapter_id: UUID,
        user_id: UUID,
        request: ConsistencyRequest,
    ) -> ConsistencyResponse:
        """Run consistency check focused on a single chapter.

        Compares a single chapter against KB entity data and optionally
        other chapters in the novel. Useful for targeted checking after
        a writing session.

        Args:
            novel_id: The novel containing the chapter.
            chapter_id: The chapter to analyze.
            user_id: The user requesting analysis (for access control).
            request: Check parameters (check types, KB inclusion).

        Returns:
            Consistency response scoped to the single chapter.

        Raises:
            narrare_core.shared.errors.NotFoundError: If novel or chapter
                does not exist.
            narrare_core.shared.errors.ForbiddenError: If user does not
                have access to the novel.
        """
        ...


@runtime_checkable
class ConsistencyOrchestratorProtocol(Protocol):
    """Protocol for ADR-044 staged consistency orchestration.

    The orchestrator is internal to the consistency service. It preserves
    the external ``ConsistencyCheckerProtocol`` response type while splitting
    work into fact extraction and consistency analysis stages.
    """

    async def run_staged_check(
        self,
        *,
        novel_id: UUID,
        deps: ConsistencyDeps,
        kb_summaries: list[dict[str, object]],
        timeline_envelopes: list[TimelineEventEnvelope],
        language: str,
        max_chapter_tokens: int,
    ) -> ConsistencyResponse:
        """Run Stage 1 and Stage 2, returning the final response."""
        ...

    def stream_staged_check(
        self,
        *,
        novel_id: UUID,
        deps: ConsistencyDeps,
        kb_summaries: list[dict[str, object]],
        timeline_envelopes: list[TimelineEventEnvelope],
        language: str,
        max_chapter_tokens: int,
    ) -> AsyncIterator[ConsistencyStageEvent | ConsistencyResponse]:
        """Stream stage progress events and the final response."""
        ...
