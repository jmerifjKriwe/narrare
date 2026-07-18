"""Protocol contracts for the memory subsystem.

Defines the interfaces that memory adapters must implement.
All implementations are injected via constructor (DI pattern).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from narrare_core.memory.consistency_models import (
        ConsistencyDismissalRecord,
        DismissalMatch,
    )
    from narrare_core.memory.models import (
        FeedbackEvent,
        PreferenceProfile,
    )


class FeedbackCollector(Protocol):
    """Collects and retrieves user feedback on AI suggestions."""

    async def record(self, event: FeedbackEvent) -> None:
        """Persist a feedback event."""
        ...

    async def get_history(
        self,
        user_id: object,
        project_id: object,
        *,
        limit: int = 100,
    ) -> list[FeedbackEvent]:
        """Retrieve recent feedback events for a user/project pair."""
        ...


class PreferenceProvider(Protocol):
    """Provides aggregated user preferences derived from feedback."""

    async def get_preferences(
        self,
        user_id: object,
        project_id: object,
    ) -> PreferenceProfile:
        """Return the current preference profile for a user/project pair."""
        ...

    async def reset(self, user_id: object, project_id: object) -> None:
        """Clear stored preferences for a user/project pair."""
        ...


class SessionMemoryCollector(Protocol):
    """Stores and retrieves cross-session writing context via mem0.

    Gives the writing pipeline memory of past writing sessions
    (e.g. "User wrote chapter 7 with a cliffhanger ending") so each
    session starts with recall of past writing decisions.
    """

    async def record_writing_session(
        self,
        user_id: object,
        project_id: object,
        *,
        mode: str,
        chapter_title: str,
        word_count: int,
    ) -> None:
        """Record a writing-session summary to mem0 (best-effort)."""
        ...

    async def get_cross_session_context(
        self,
        user_id: object,
        project_id: object,
    ) -> str:
        """Retrieve past writing-session memories as formatted context text."""
        ...


class ConsistencyFeedbackCollector(Protocol):
    """Stores and semantically retrieves dismissed consistency findings.

    Adds a cross-run learning layer on top of the per-novel exact-fingerprint
    DB dismiss (CR-AUFG-07-26). The DB layer suppresses findings whose
    ``fingerprint`` (``description::entity_names``) matches exactly; this
    protocol adds *semantic* suppression so findings whose fingerprint
    shifted across runs (the LLM rephrased the description) but whose meaning
    is unchanged are still recognised as already-dismissed.

    Storage scope is user+project (mirrors ``FeedbackCollector`` /
    ``SessionMemoryCollector``): ``user_id`` → mem0 ``user_id``,
    ``project_id`` → mem0 ``agent_id``. Suppression is therefore within-novel
    by default — the safe choice, because consistency findings reference one
    novel's entities/lore and a false positive in novel A is rarely a false
    positive in novel B. The record carries ``user_id`` regardless, so
    cross-novel learning is a future retrieve-filter change with no data
    migration.

    Privacy (ADR-045 Decision 8, RULE-22): only the finding *description*
    (structural analysis output) and linkage metadata are recorded — never
    raw draft prose. This matches the ``SessionMemoryService`` structural-
    metadata rule. All operations are best-effort (RULE-11): mem0 failures
    are logged warnings, never raised, so the dismiss + consistency flows
    never degrade because the learning layer is unavailable.

    See:
        :mod:`narrare_core.memory.consistency_feedback_service` — the
        mem0-backed implementation (Core specialist, follows
        ``feedback_service.py`` / ``session_memory_service.py``).
        CR-AUFG-03-10 design note.
    """

    async def record_dismissal(
        self,
        user_id: object,
        project_id: object,
        record: ConsistencyDismissalRecord,
    ) -> None:
        """Forward a dismissal to mem0 for cross-run learning (best-effort).

        Called by the API-layer dismiss service *after* the per-novel DB
        persist (07-26) succeeds, mirroring ``FeedbackService.record``'s
        dual-store pattern. Never raises: mem0 write failures are warnings.
        """
        ...

    async def find_similar_dismissals(
        self,
        user_id: object,
        project_id: object,
        *,
        finding_description: str,
        limit: int = 10,
        similarity_threshold: float = 0.85,
    ) -> list[DismissalMatch]:
        """Retrieve past dismissals semantically similar to a finding.

        Queries mem0 (pgvector hybrid search) scoped to user+project and
        returns matches above ``similarity_threshold``, best-first. Used by
        the consistency-check flow to de-prioritise/suppress findings the
        user has already dismissed.

        Returns an empty list when mem0 is unavailable or returns nothing
        (graceful degradation, RULE-11).
        """
        ...


class MemoryFacade(Protocol):
    """Combined memory interface: feedback collection + preference retrieval.

    Implementations provide both feedback tracking and preference derivation
    in a single object, simplifying DI wiring at the service layer.
    """

    async def record(self, event: FeedbackEvent) -> None:
        """Persist a feedback event."""
        ...

    async def get_history(
        self,
        user_id: object,
        project_id: object,
        *,
        limit: int = 100,
    ) -> list[FeedbackEvent]:
        """Retrieve recent feedback events for a user/project pair."""
        ...

    async def get_preferences(
        self,
        user_id: object,
        project_id: object,
    ) -> PreferenceProfile:
        """Return the current preference profile for a user/project pair."""
        ...

    async def reset(self, user_id: object, project_id: object) -> None:
        """Clear stored preferences for a user/project pair."""
        ...
