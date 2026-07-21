"""Pydantic schemas for the adaptive REST API (ADR-069 D12).

Request/response models for the three adaptive endpoints:
- GET  /api/v1/adaptive/{project_id}/context   → AdaptiveContextResponse
- POST /api/v1/adaptive/{project_id}/toggle    (AdaptiveToggleInput) → AdaptiveSettingsResponse
- POST /api/v1/adaptive/{project_id}/weights   (AdaptiveWeightsInput) → AdaptiveSettingsResponse

AdaptiveWeightsInput.validated() clamps each weight to [0.0, 1.0], mirroring
the Core ``AdaptiveWeights.validated()`` method. Persistence serialises via
``AdaptiveSettingsRepository`` to the ``ProjectSettings.adaptive_settings``
JSONB column (Phase 3 Task 1).

See:
    ADR-069 Decision 2 (persistence), Decision 12 (Service Layer),
    CONSTRAINTS.md RULE-03, RULE-04.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AdaptiveWeightsResponse(BaseModel):
    """Adaptive weights in an API response (clamped, read-only)."""

    model_config = ConfigDict(frozen=True)

    preference: float = Field(default=0.7, ge=0.0, le=1.0)
    voice_fidelity: float = Field(default=0.9, ge=0.0, le=1.0)
    style_constraints: float = Field(default=1.0, ge=0.0, le=1.0)
    avoidance: float = Field(default=1.0, ge=0.0, le=1.0)


class AdaptiveWeightsInput(BaseModel):
    """Adaptive weights in a POST body (pre-clamping; may be out of range).

    Call ``.validated()`` to obtain a clamped copy. The service clamps
    before persistence — the API accepts any float and returns the clamped
    value in the response.
    """

    model_config = ConfigDict(extra="forbid")

    preference: float = Field(default=0.7)
    voice_fidelity: float = Field(default=0.9)
    style_constraints: float = Field(default=1.0)
    avoidance: float = Field(default=1.0)

    def validated(self) -> AdaptiveWeightsInput:
        """Return a copy with each weight clamped to [0.0, 1.0]."""
        return self.model_copy(
            update={
                "preference": max(0.0, min(1.0, self.preference)),
                "voice_fidelity": max(0.0, min(1.0, self.voice_fidelity)),
                "style_constraints": max(0.0, min(1.0, self.style_constraints)),
                "avoidance": max(0.0, min(1.0, self.avoidance)),
            }
        )


class AdaptiveToggleInput(BaseModel):
    """Body for POST /adaptive/{project_id}/toggle."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool


class AdaptiveSourceSummary(BaseModel):
    """Adaptive source data rendered for the dashboard."""

    model_config = ConfigDict(frozen=True)

    preference_text: str = ""
    voice_profiles_text: str = ""
    style_constraints_text: str = ""
    avoidance_patterns_text: str = ""


class AdaptiveContextResponse(BaseModel):
    """Response for GET /adaptive/{project_id}/context."""

    model_config = ConfigDict(frozen=True)

    project_id: str
    enabled: bool
    weights: AdaptiveWeightsResponse
    sources: AdaptiveSourceSummary
    has_any_signal: bool


class AdaptiveSettingsResponse(BaseModel):
    """Response for POST /toggle and POST /weights — the new persisted state."""

    model_config = ConfigDict(frozen=True)

    enabled: bool
    weights: AdaptiveWeightsResponse = Field(default_factory=AdaptiveWeightsResponse)
