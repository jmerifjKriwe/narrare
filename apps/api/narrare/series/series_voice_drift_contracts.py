"""Series voice-drift service contract — SeriesVoiceDriftServiceProtocol (Spec 4 Task 3).

The series-scope analogue of
:class:`~narrare.analysis.author_voice_drift_service.AuthorVoiceDriftService`
(ANAL-009 Phase 2B). Where the novel-level service compares a band's per-chapter
narrator metrics against the **novel's** stored
:class:`AuthorVoiceProfile` (``ProjectSettings.author_voice``), this service
compares them against the **series voice** (``SeriesSettings.author_voice``,
established in Spec 3 / ADR-078). This is the cross-novel drift signal: does
band N's narrator voice drift away from the series-wide voice baseline?

The service REUSES the existing analysis pipeline helpers verbatim
(:func:`compute_author_voice_per_chapter`,
:func:`analyse_author_voice_drift`) — the only difference is the SOURCE of the
reference profile + metric group (series settings vs novel settings). No new
agent is created (RULE-01b: the existing ``AuthorVoiceDriftAgent`` is the LLM
surface). The pipeline is **read-only** (ADR-073 Decision 5).

**Regression safety (CRITICAL):** the novel-level
:class:`AuthorVoiceDriftService` and its ``POST /analysis/author-voice-drift/
{novel_id}`` SSE endpoint are 100% unchanged. A standalone novel (no series
voice) keeps its existing behaviour. This service is a SEPARATE series-scoped
endpoint (``POST /api/v1/series/{id}/voice-drift/check``) so the two never
interact.

RULE-11 graceful degradation: a series with no stored voice profile, a profile
missing the metric blocks, or a novel with no chapter prose yields a graceful
``no_profile`` response (never a crash) — mirroring the novel-level service.

Ownership contract (C1 / anti-enumeration — mirrors
:meth:`SeriesVoiceService._verify_series_ownership`): the single method takes
``user_id`` and verifies the caller owns the series BEFORE any read, then
verifies the novel belongs to the series. Both surface as ``ForbiddenError``
(HTTP 403, never 404).

See:
    :mod:`narrare.series.series_voice_drift_service` — implementation.
    :mod:`narrare.analysis.author_voice_drift_service` — the novel-level parallel.
    ADR-078 — Series Voice Hierarchy (Delta model).
    ADR-074 — Author Voice Storage Contract (the pipeline reused).
    CONSTRAINTS.md RULE-03 / RULE-06 / RULE-07 / RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.analysis.schemas_author_voice_drift import (
        AuthorVoiceDriftRequest,
        AuthorVoiceDriftResponse,
    )


@runtime_checkable
class SeriesVoiceDriftServiceProtocol(Protocol):
    """Protocol for the Spec 4 series-scope voice-drift analysis service.

    Delegates to the SAME Core-layer
    :class:`~narrare_core.agents.author_voice_drift_agent.AuthorVoiceDriftAgent`
    as the novel-level service, but uses the series voice profile
    (``SeriesSettings.author_voice``) as the trend baseline instead of the
    novel's stored profile. One LLM call per check.

    The service is **read-only**: it never writes to ``SeriesSettings`` or
    ``ProjectSettings``. The series voice profile is read via
    :class:`SeriesRepository` (``get_settings``).

    RULE-11 graceful degradation: no stored series voice, a profile missing the
    metric blocks, or no chapter with prose yields a graceful ``no_profile``
    response.
    """

    async def check(
        self,
        series_id: UUID,
        novel_id: UUID,
        user_id: UUID,
        request: AuthorVoiceDriftRequest,
    ) -> AuthorVoiceDriftResponse:
        """Analyse a band's narrator drift against the series voice baseline.

        Loads the series voice profile from ``SeriesSettings.author_voice``,
        extracts the metric blocks (voice + author), computes the per-chapter
        narrator trend + jumps against the SERIES baseline, runs the governed
        ``author_voice_drift`` agent (1 LLM call), and returns the aggregate
        response carrying the narrator drift result (or a graceful
        ``no_profile`` when the series voice cannot be analysed).

        Args:
            series_id: The series whose voice is the drift baseline.
            novel_id: The novel (band) whose chapters are analysed. MUST belong
                to ``series_id`` (else ``ForbiddenError``).
            user_id: The caller (ownership verified, anti-enumeration).
            request: Optional filter (``chapter_ids`` to scope to specific
                chapters; ``None`` / empty means all chapters).

        Returns:
            The :class:`AuthorVoiceDriftResponse` (reused from the novel-level
            schema, RULE-22) carrying either the narrator drift ``result`` or a
            ``no_profile`` skip detail (mutually exclusive).

        Raises:
            narrare_core.shared.errors.ForbiddenError: Series missing/not owned
                by ``user_id``, or novel not in ``series_id`` (403,
                anti-enumeration — never 404).
            narrare_core.shared.errors.NotFoundError: Novel missing, or no model
                config resolved for the analysis category.
            narrare_core.shared.errors.ConfigurationError: No ``PromptComposer``
                configured.
        """
        ...
