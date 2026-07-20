"""Adaptive Context — consolidated view of all adaptivity signals.

Defines the Core data models for adaptivity:
- ``AdaptiveWeights``: user-tunable weighting of signal sources.
- ``AdaptiveContext``: consolidated snapshot of all adaptive data for one
  specific AI invocation.
- ``AdaptiveSettings``: persisted user settings (enabled flag + weights).

Pure value objects — no I/O, no dependencies on apps/.

See:
    ADR-069 (Adaptive Context + Dialogue Coach Vertical),
    CONSTRAINTS.md RULE-03 (Contracts first), RULE-04 (Modularise).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class AdaptiveWeights:
    """User-tunable weighting of adaptivity signals.

    All values are floats in ``[0.0, 1.0]``. The exact semantics are
    determined by the ``AdaptiveContextEnricher``; typically a higher
    weight controls how strongly the corresponding signal is injected
    into the prompt (e.g., as an explicit instruction vs. context block).

    Attributes:
        preference: Weight for user preferences (PreferenceProfile).
            Default ``0.7`` — preferences are primary.
        voice_fidelity: Weight for character-voice fidelity
            (CharacterVoiceProfile). Default ``0.9`` — voice fidelity is
            critical for dialogue-coach use cases.
        style_constraints: Weight for hard style constraints.
            Default ``1.0`` — constraints are binding.
        avoidance: Weight for avoidance patterns (things the user
            rejects). Default ``1.0`` — avoidance is binding.
    """

    preference: float = 0.7
    voice_fidelity: float = 0.9
    style_constraints: float = 1.0
    avoidance: float = 1.0

    def validated(self) -> AdaptiveWeights:
        """Return a copy with each weight clamped to ``[0.0, 1.0]``.

        Does not mutate ``self`` (the dataclass is frozen). Use this at
        any boundary where untrusted input (REST API, JSONB load) may
        have produced out-of-range values.
        """
        return AdaptiveWeights(
            preference=max(0.0, min(1.0, self.preference)),
            voice_fidelity=max(0.0, min(1.0, self.voice_fidelity)),
            style_constraints=max(0.0, min(1.0, self.style_constraints)),
            avoidance=max(0.0, min(1.0, self.avoidance)),
        )


@dataclass(frozen=True, slots=True)
class AdaptiveContext:
    """Consolidated snapshot of all adaptive signals for one invocation.

    Assembled by the ``AdaptiveContextProvider`` (Backend impl) and
    consumed by the ``AdaptiveContextEnricher`` (Core), which injects
    the four text fields into ``dynamic_inputs`` for prompt composition.

    ADR-055/057 boundary: ``voice_profiles_text`` carries ONLY the
    descriptive ``formatted_voice_profiles`` text (the
    ``speech_summary`` block). The numeric ``voice_metrics`` are
    checking-path only and never reach this dataclass.

    Attributes:
        user_id: The user ID the context applies to.
        project_id: The project ID the context applies to.
        preference_text: Formatted text from PreferenceProfile
            (may be empty if no preferences).
        voice_profiles_text: Formatted text of all CharacterVoiceProfiles
            (may be empty if no profiles).
        style_constraints_text: Derived style constraints as a
            bullet list (may be empty).
        avoidance_patterns_text: Derived avoidance patterns as a
            bullet list (may be empty).
        weights: The weights active at invocation time.
        source_summary: Short human-readable summary of sources
            (e.g., "3 character voices, 12 preference events") for
            transparency UI and logging.
    """

    user_id: UUID
    project_id: UUID
    preference_text: str = ""
    voice_profiles_text: str = ""
    style_constraints_text: str = ""
    avoidance_patterns_text: str = ""
    weights: AdaptiveWeights = field(default_factory=AdaptiveWeights)
    source_summary: str = ""

    @property
    def has_any_signal(self) -> bool:
        """True if at least one adaptive signal is present."""
        return bool(
            self.preference_text
            or self.voice_profiles_text
            or self.style_constraints_text
            or self.avoidance_patterns_text
        )


@dataclass(frozen=True, slots=True)
class AdaptiveSettings:
    """Persisted user settings for adaptivity.

    Stored per-project as JSONB on ``ProjectSettings.adaptive_settings``
    (Phase 3 / ADR-069 Decision 2). Phase 2 ships a scaffold impl that
    returns defaults only.

    Attributes:
        enabled: Master switch. When ``False``, the
            ``AdaptiveContextEnricher`` short-circuits and writes no
            adaptive variables (graceful no-op).
        weights: Active weight configuration.
    """

    enabled: bool = True
    weights: AdaptiveWeights = field(default_factory=AdaptiveWeights)
