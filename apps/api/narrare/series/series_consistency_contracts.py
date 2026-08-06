"""Series-consistency service contract — SeriesConsistencyServiceProtocol (Spec 4 Task 2).

The series-consistency service detects contradictions between a band's (novel's)
chapter prose and the series **Canon KB** — the cross-novel fixed-facts layer
established in Spec 1. It is the Layer-3 orchestrator of the
:class:`~narrare_core.agents.series_consistency_agent.SeriesConsistencyAgent`
(Task 1): it loads the Series-Canon entries via
:meth:`KBRepository.find_canon_for_series` (Spec 1), loads the band's chapters,
resolves the governed ``series_consistency`` system prompt via
:class:`PromptComposer` (RULE-02b / ADR-054 Mode 1), and runs the agent —
**one LLM call per check**. An empty conflicts list means no contradictions
were found (a valid and common result).

This is distinct from the per-novel
:class:`~narrare.kb.consistency_service.KBConsistencyService` (CONS-001, which
checks *within* a novel: entry-internal + relationship asymmetry + cross-entity).
This service checks *novel-vs-series-Canon*.

The check is **read-only and stateless** in this slice: it runs the agent and
returns the conflicts; it does not persist results (a future slice may add the
``GET …/consistency/{novel_id}`` retrieval endpoint + a results repository, per
the Spec 4 plan Task 2 stretch).

Ownership contract (C1 / anti-enumeration — mirrors
:meth:`SeriesVoiceService._verify_series_ownership`): the single method takes
``user_id`` and verifies the caller owns the series BEFORE any read. A *missing*
series and a *not-owned* series BOTH surface as ``ForbiddenError`` (HTTP 403) —
never ``NotFoundError`` (404) — so series ids are not enumerable. The method
additionally verifies the novel belongs to the series.

A separate Protocol file (not appended to ``series/contracts.py``) keeps that
197-line file under the RULE-04 limit and keeps series-consistency concerns
self-contained (RULE-06: one responsibility per file). Mirrors the
``series_voice_contracts.py`` extraction precedent.

See:
    :mod:`narrare.series.series_consistency_service` — implementation.
    :mod:`narrare.series.series_consistency_schemas` — request/response DTOs.
    ADR-075 — Series Foundation (Canon KB scope).
    CONSTRAINTS.md RULE-03 / RULE-06 / RULE-07 / RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.series.series_consistency_schemas import SeriesConsistencyCheckResponse


@runtime_checkable
class SeriesConsistencyServiceProtocol(Protocol):
    """Protocol for the Spec 4 series-consistency (canon-contradiction) service.

    One operation backs the Series Consistency API (Task 2):

    - ``check_novel`` — verify novel in series → fetch Canon entries + chapters →
      run :class:`SeriesConsistencyAgent` (1 LLM call) → return conflicts.

    All dependencies are injected (RULE-07). Ownership + novel-membership are
    verified inside the service (mirrors :class:`SeriesVoiceService`) so the
    contract is enforced even when called from non-request contexts.
    """

    async def check_novel(
        self,
        series_id: UUID,
        novel_id: UUID,
        user_id: UUID,
    ) -> SeriesConsistencyCheckResponse:
        """Check a band's chapter prose against the series Canon KB.

        Loads the Series-Canon entries
        (``KBRepository.find_canon_for_series``) + the band's chapters
        (``ChapterRepository.list_by_novel``), resolves the governed
        ``series_consistency`` system prompt (Mode 1), and runs the
        :class:`SeriesConsistencyAgent`. An empty ``conflicts`` list means no
        contradictions were found.

        RULE-11 graceful degradation: a series with no Canon entries OR a novel
        with no chapter prose yields an empty-conflicts result **without an LLM
        call** (the agent has nothing to check — mirrors
        :meth:`BandSummaryService.generate` failing fast on no summaries).

        Args:
            series_id: The series whose Canon is the reference.
            novel_id: The novel (band) whose chapters are checked. MUST belong
                to ``series_id`` (else ``ForbiddenError``).
            user_id: The caller (ownership verified, anti-enumeration).

        Returns:
            The :class:`SeriesConsistencyCheckResponse` carrying the conflicts
            (possibly empty) + the agent summary + the canon/chapter counts
            (transparency for the UI).

        Raises:
            narrare_core.shared.errors.ForbiddenError: Series missing/not owned
                by ``user_id``, or novel not in ``series_id`` (403,
                anti-enumeration — never 404).
            narrare_core.shared.errors.NotFoundError: No model config resolved
                for the analysis category.
            narrare_core.shared.errors.ConfigurationError: No ``PromptComposer``
                configured.
            narrare_core.shared.errors.WritingError: The LLM call failed.
        """
        ...
