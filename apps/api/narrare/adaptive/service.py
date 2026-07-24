"""AdaptiveContextService — Backend Service Layer for the dashboard (ADR-069 D12).

Implements ``AdaptiveContextServiceProtocol`` (Task 3). Three operations:
- ``get_context()`` — read the current adaptive state for the dashboard.
- ``set_enabled()`` — toggle adaptivity on/off for the project.
- ``set_weights()`` — update + clamp the four adaptive weights.

The service delegates to the Core ``AdaptiveContextProvider`` Protocol
(Phase 1; Backend impl in ``adaptive_context_provider.py``) for the read
path and to ``AdaptiveSettingsRepository`` for persistence. It never
touches SQL or mem0 directly (RULE-07 / RULE-08).

RULE-11 graceful degradation: if the provider returns no signals, the
response carries empty source text + ``has_any_signal=False`` (the
dashboard shows the "no signals yet" state). If persistence fails, the
existing exception surfaces to the router's error handler — no silent
swallowing.

See:
    ADR-069 Decision 12 (Provider vs Service separation),
    CONSTRAINTS.md RULE-03 / RULE-06 / RULE-07 / RULE-11 / RULE-12.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

from narrare.adaptive.schemas import (
    AdaptiveContextResponse,
    AdaptiveSettingsResponse,
    AdaptiveSnapshotItem,
    AdaptiveSnapshotsResponse,
    AdaptiveSourceSummary,
    AdaptiveWeightsInput,
    AdaptiveWeightsResponse,
)
from narrare_core.ai_invocation.adaptive_context import (
    AdaptiveSettings,
    AdaptiveWeights,
)

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.adaptive.contracts import AdaptiveSettingsRepositoryProtocol
    from narrare_core.ai_invocation.adaptive_contracts import (
        AdaptiveContextProvider,
    )
    from narrare_core.ai_invocation.evidence_models import (
        FeatureInvocationEvidence,
    )

    class EvidenceSnapshotReader(Protocol):
        """Read-port for adaptive snapshot evidence (ADR-070).

        Narrow structural type so the service depends on a Protocol, not
        the concrete ``EvidenceRepositoryImpl`` (RULE-03 / RULE-08). Mirrors
        ``EvidenceRepositoryImpl.get_adaptive_snapshots``.
        """

        async def get_adaptive_snapshots(
            self,
            novel_id: UUID,
            *,
            limit: int = 20,
        ) -> list[FeatureInvocationEvidence]: ...


def _weights_to_response(
    enabled: bool,
    weights: AdaptiveWeights,
) -> AdaptiveSettingsResponse:
    return AdaptiveSettingsResponse(
        enabled=enabled,
        weights=AdaptiveWeightsResponse(
            preference=max(0.0, min(1.0, weights.preference)),
            voice_fidelity=max(0.0, min(1.0, weights.voice_fidelity)),
            style_constraints=max(0.0, min(1.0, weights.style_constraints)),
            avoidance=max(0.0, min(1.0, weights.avoidance)),
        ),
    )


def _snapshot_item(record: FeatureInvocationEvidence) -> AdaptiveSnapshotItem:
    """Map a FeatureInvocationEvidence row to an AdaptiveSnapshotItem (ADR-070).

    Weights are clamped to [0.0, 1.0] defensively; missing keys default to
    0.0. ``created_at`` falls back to ``now`` for legacy rows without a
    DB-stamped timestamp.
    """
    weights: AdaptiveWeightsResponse | None = None
    if record.adaptive_weights is not None:
        w = record.adaptive_weights
        weights = AdaptiveWeightsResponse(
            preference=max(0.0, min(1.0, w.get("preference", 0.0))),
            voice_fidelity=max(0.0, min(1.0, w.get("voice_fidelity", 0.0))),
            style_constraints=max(0.0, min(1.0, w.get("style_constraints", 0.0))),
            avoidance=max(0.0, min(1.0, w.get("avoidance", 0.0))),
        )
    return AdaptiveSnapshotItem(
        invocation_id=str(record.invocation_id) if record.invocation_id else None,
        novel_id=str(record.novel_id) if record.novel_id else None,
        intent=record.intent,
        mode=record.mode,
        created_at=record.created_at if record.created_at is not None else datetime.now(UTC),
        source_summary=record.adaptive_source_summary,
        weights=weights,
    )


class AdaptiveContextService:
    """Backend service for the Adaptivity Dashboard (LEARN-002).

    Args:
        provider: AdaptiveContextProvider — Phase 1 Protocol; the Backend
            impl composes PreferenceProvider + ProfileProvider +
            AdaptiveSettingsRepository.
        settings_repo: AdaptiveSettingsRepositoryProtocol for persistence.
            The provider also uses this for ``get_settings()``, but the
            service uses it directly for writes (toggle / weights).
        evidence_repo: EvidenceSnapshotReader — read-port for adaptive
            snapshot evidence (ADR-070); used by ``get_adaptive_snapshots``.
    """

    def __init__(
        self,
        provider: AdaptiveContextProvider,
        settings_repo: AdaptiveSettingsRepositoryProtocol,
        evidence_repo: EvidenceSnapshotReader,
    ) -> None:
        self._provider = provider
        self._settings_repo = settings_repo
        self._evidence_repo = evidence_repo

    async def get_context(
        self,
        project_id: UUID,
        user_id: UUID,
    ) -> AdaptiveContextResponse:
        """Read the current adaptive state for the dashboard."""
        ctx = await self._provider.get_context(user_id=user_id, project_id=project_id)
        settings = await self._provider.get_settings(user_id=user_id, project_id=project_id)
        return AdaptiveContextResponse(
            project_id=str(project_id),
            enabled=settings.enabled,
            weights=AdaptiveWeightsResponse(
                preference=settings.weights.preference,
                voice_fidelity=settings.weights.voice_fidelity,
                style_constraints=settings.weights.style_constraints,
                avoidance=settings.weights.avoidance,
            ),
            sources=AdaptiveSourceSummary(
                preference_text=ctx.preference_text,
                voice_profiles_text=ctx.voice_profiles_text,
                style_constraints_text=ctx.style_constraints_text,
                avoidance_patterns_text=ctx.avoidance_patterns_text,
            ),
            has_any_signal=ctx.has_any_signal,
        )

    async def set_enabled(
        self,
        project_id: UUID,
        user_id: UUID,
        enabled: bool,
    ) -> AdaptiveSettingsResponse:
        """Toggle adaptivity on/off for the project; persist + return new state."""
        current = await self._settings_repo.load(project_id)
        if current is None:
            current = AdaptiveSettings(enabled=enabled, weights=AdaptiveWeights())
        else:
            current = AdaptiveSettings(enabled=enabled, weights=current.weights)
        await self._settings_repo.save(project_id, current)
        return _weights_to_response(current.enabled, current.weights)

    async def set_weights(
        self,
        project_id: UUID,
        user_id: UUID,
        weights: AdaptiveWeightsInput,
    ) -> AdaptiveSettingsResponse:
        """Update adaptive weights (clamped); persist + return new state."""
        clamped = weights.validated()
        current = await self._settings_repo.load(project_id)
        enabled = current.enabled if current is not None else True
        new_settings = AdaptiveSettings(
            enabled=enabled,
            weights=AdaptiveWeights(
                preference=clamped.preference,
                voice_fidelity=clamped.voice_fidelity,
                style_constraints=clamped.style_constraints,
                avoidance=clamped.avoidance,
            ),
        )
        await self._settings_repo.save(project_id, new_settings)
        return _weights_to_response(new_settings.enabled, new_settings.weights)

    async def get_adaptive_snapshots(
        self,
        project_id: UUID,
        user_id: UUID,
        limit: int = 20,
    ) -> AdaptiveSnapshotsResponse:
        """List recent adaptive snapshots for the dashboard (ADR-070).

        project_id is the novel UUID (novel ≡ project); it is passed to the
        evidence repository as novel_id. Ownership is gated at the REST
        boundary (auth + novel ownership), mirroring the other adaptive
        endpoints.
        """
        del user_id  # ownership handled at router; read scoped by novel_id.
        records = await self._evidence_repo.get_adaptive_snapshots(project_id, limit=limit)
        items = [_snapshot_item(r) for r in records]
        return AdaptiveSnapshotsResponse(
            project_id=str(project_id),
            items=items,
        )
