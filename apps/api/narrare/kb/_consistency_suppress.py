"""Suppress issues that match a past dismissal in mem0 (CR-AUFG-03-10).

Pure orchestration helper extracted from
:class:`narrare.kb.consistency_service.KBConsistencyService` to keep that
service under the RULE-04 file-size limit and make the suppression policy
independently testable. Owns exactly one responsibility: decide which
freshly-produced issues to hide because the user previously dismissed a
semantically-equivalent finding.

Best-effort (RULE-11): when mem0 is unavailable (``feedback_memory is
None``), when the caller did not authenticate a user (``user_id is None``),
or when a mem0 query raises, suppression is skipped — the issue stays
visible. Over-suppression (hiding a real finding) is the higher-cost
error, so the helper fails open.

The per-call mem0 failure handling here is defence-in-depth on top of
:func:`narrare_core.memory.consistency_feedback_service.
ConsistencyFeedbackService.find_similar_dismissals`, which already swallows
mem0 errors and returns ``[]``. The outer try/except guards against a
future contract regression or a non-mem0 exception type leaking through.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.worldbuilding_contracts import ConsistencyIssue
    from narrare_core.memory.protocols import ConsistencyFeedbackCollector

logger = structlog.get_logger(__name__)


async def suppress_dismissed_issues(
    issues: list[ConsistencyIssue],
    feedback_memory: ConsistencyFeedbackCollector | None,
    user_id: str | None,
    project_id: UUID,
) -> tuple[list[ConsistencyIssue], int]:
    """Filter out issues that match a past dismissal in mem0.

    Args:
        issues: Freshly-produced consistency issues (already sorted by
            severity by the caller — order is preserved in the output).
        feedback_memory: Optional mem0-backed dismissal collector. ``None``
            disables suppression (passthrough).
        user_id: Authenticated user identifier for mem0 scoping. ``None``
            disables suppression (no identity to scope by).
        project_id: The novel/project to scope the mem0 query to.
            Within-novel suppression is the safe default (CR-AUFG-03-10).

    Returns:
        Tuple of ``(kept_issues, suppressed_count)``. ``suppressed_count`` is
        the number of issues filtered out — surfaced to the UI via
        ``ConsistencyCheckResponse.suppressed_count`` so the user can see
        "N known false positives hidden".
    """
    if feedback_memory is None or user_id is None or not issues:
        return issues, 0

    kept: list[ConsistencyIssue] = []
    suppressed_count = 0
    for issue in issues:
        if await _has_similar_dismissal(feedback_memory, user_id, project_id, issue.description):
            suppressed_count += 1
            continue
        kept.append(issue)
    return kept, suppressed_count


async def _has_similar_dismissal(
    feedback_memory: ConsistencyFeedbackCollector,
    user_id: str,
    project_id: UUID,
    finding_description: str,
) -> bool:
    """Return True if mem0 holds a dismissal similar to ``finding_description``.

    Best-effort (RULE-11): on any exception the helper returns ``False``
    (no match) so the issue stays visible. Logs a single warning per
    failure so flaky mem0 does not silently hide findings.
    """
    try:
        matches = await feedback_memory.find_similar_dismissals(
            user_id,
            project_id,
            finding_description=finding_description,
        )
    except Exception:
        logger.warning(
            "consistency_suppress_query_failed",
            project_id=str(project_id),
        )
        return False
    return bool(matches)
