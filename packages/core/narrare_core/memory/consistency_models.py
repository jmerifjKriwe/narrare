"""Consistency-feedback-loop record models for the memory subsystem.

Holds the structured inputs/outputs for the cross-run, cross-session
consistency-dismissal learning layer (CR-AUFG-03-10). These records live
in Core (RULE-07) so the Core memory service and the API-layer dismiss
service can share one contract. The API layer maps its enum-typed
``ConsistencyIssue`` / ``DismissFindingRequest`` onto these ``str``-typed
cores (mirrors how ``FeedbackEvent.intent`` is a plain ``str``).

Split out of ``models.py`` to respect RULE-04 (modularise, do not
compress): each module owns one coherent responsibility. The feedback,
preference, and learning models remain in ``models.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ConsistencyDismissalRecord:
    """A user-dismissed consistency finding, forwarded to mem0 for learning.

    The per-novel DB dismiss (CR-AUFG-07-26, ``DismissedFinding``) already
    persists exact-fingerprint dismissals per novel. This record carries the
    extra context mem0 needs to learn *semantic* dismissals: findings whose
    ``fingerprint`` shifted across runs (LLM rephrased the description) but
    whose meaning is unchanged. mem0's pgvector backend matches such
    near-duplicates by embedding similarity.

    Privacy (ADR-045 Decision 8, RULE-22): stores the finding *description*
    (a structural analysis output referencing KB entities — analogous to the
    structural chapter-title metadata ``SessionMemoryService`` stores), never
    raw draft prose. This is the user's own worldbuilding analysis on a
    local-first store (ADR-033), so it is in-scope.

    Attributes:
        user_id: The dismissing user (mem0 ``user_id`` scope).
        project_id: The novel (mem0 ``agent_id`` scope). Scoped to user+
            project so suppression stays within-novel; cross-novel learning
            is a future toggle (broaden the filter) that needs no data change.
        fingerprint: The stable finding key (``description::entity_names``),
            identical to the 07-26 DB fingerprint — links the two layers.
        finding_description: The finding's human-readable description text.
            This is the field matched semantically by mem0.
        entity_names: The entity names involved in the finding (context).
        category: Consistency-category string (e.g. ``"entry_internal"``).
            Plain ``str`` because the enum lives in the API layer (RULE-07).
        severity: Severity string (e.g. ``"major"``). Plain ``str`` (RULE-07).
        reason: Optional user-provided reason for the dismissal.
        dismissed_at: When the dismissal happened.
    """

    user_id: UUID
    project_id: UUID
    fingerprint: str
    finding_description: str
    entity_names: list[str]
    category: str
    severity: str
    reason: str | None = None
    dismissed_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
    )


@dataclass(frozen=True, slots=True)
class DismissalMatch:
    """A semantically-retrieved past dismissal, scored against a new finding.

    Returned by :meth:`ConsistencyFeedbackCollector.find_similar_dismissals`.
    The consistency-check flow uses the ``similarity`` score to decide whether
    a newly-produced finding should be de-prioritised or suppressed.
    """

    fingerprint: str
    finding_description: str
    similarity: float  # 0.0-1.0, from mem0 hybrid/embedding search
    reason: str | None = None
