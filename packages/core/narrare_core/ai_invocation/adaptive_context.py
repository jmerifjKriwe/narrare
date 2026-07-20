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

from dataclasses import dataclass


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
