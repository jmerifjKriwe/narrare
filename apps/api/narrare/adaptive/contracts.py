"""AdaptiveContextService Protocol — Backend REST API contract (ADR-069 D12).

Distinct from the Core ``AdaptiveContextProvider`` Protocol (Phase 1,
``adaptive_contracts.py``), which serves the invocation pipeline (enricher).
This Protocol serves the dashboard REST API — the public Service Layer
surface for WebUI / future MCP / future A2A / future CLI clients.

Service Layer is the ONLY public API (RULE-12). Both Protocols compose the
same underlying providers but expose different method shapes for different
consumers (invocation pipeline vs REST API).

See:
    ADR-069 Decision 12 (Provider vs Service separation),
    ADR-067 (composer-provider precedent),
    CONSTRAINTS.md RULE-03 (Contracts first), RULE-12 (Service Layer).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.adaptive.schemas import (
        AdaptiveContextResponse,
        AdaptiveSettingsResponse,
        AdaptiveSnapshotsResponse,
        AdaptiveWeightsInput,
    )
    from narrare_core.ai_invocation.adaptive_context import AdaptiveSettings


@runtime_checkable
class AdaptiveContextServiceProtocol(Protocol):
    """Public-API service for the Adaptivity Dashboard (LEARN-002).

    Four operations:
    - ``get_context()``: read the current adaptive state (enabled flag,
      weights, source summary) for the dashboard.
    - ``set_enabled()``: toggle adaptivity on/off for the project.
    - ``set_weights()``: update the four adaptive weights (clamped to
      ``[0.0, 1.0]``).
    - ``get_adaptive_snapshots()``: list recent adaptive evidence
      snapshots for the dashboard timeline (ADR-070; ownership-gated in
      the service, IDOR S11c).

    Implementations delegate to ``AdaptiveContextProvider`` (for the read
    path) + ``AdaptiveSettingsRepository`` (for persistence) + the
    evidence repository (snapshots). All four methods are async (DB I/O).
    """

    async def get_context(
        self,
        project_id: UUID,
        user_id: UUID,
    ) -> AdaptiveContextResponse:
        """Return the current adaptive context for the dashboard."""
        ...

    async def set_enabled(
        self,
        project_id: UUID,
        user_id: UUID,
        enabled: bool,
    ) -> AdaptiveSettingsResponse:
        """Toggle adaptivity on/off for the project; persist + return new state."""
        ...

    async def set_weights(
        self,
        project_id: UUID,
        user_id: UUID,
        weights: AdaptiveWeightsInput,
    ) -> AdaptiveSettingsResponse:
        """Update adaptive weights (clamped); persist + return new state."""
        ...

    async def get_adaptive_snapshots(
        self,
        project_id: UUID,
        user_id: UUID,
        limit: int = 20,
    ) -> AdaptiveSnapshotsResponse:
        """List recent adaptive evidence snapshots (ADR-070).

        Ownership is verified in the service before the evidence read;
        unknown/foreign projects raise ``NotFoundError``.
        """
        ...


class AdaptiveSettingsRepositoryProtocol(Protocol):
    """Repository contract for AdaptiveSettings persistence.

    Decouples AdaptiveContextService from the concrete
    AdaptiveSettingsRepository impl (RULE-03). Production wiring
    uses AdaptiveSettingsRepositoryImpl; tests use FakeAdaptiveRepo
    or MagicMock-with-spec.
    """

    async def load(self, project_id: UUID) -> AdaptiveSettings | None:
        """Load AdaptiveSettings for a project.

        Returns None when no row exists or column is NULL
        (graceful degradation per RULE-11).
        """
        ...

    async def save(self, project_id: UUID, settings: AdaptiveSettings) -> None:
        """Persist AdaptiveSettings for a project (upsert)."""
        ...
