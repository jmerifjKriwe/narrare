"""Adaptive Context Provider Protocol — Core contract for adaptivity aggregation.

Defines the Protocol that Backend implementations must satisfy to assemble
an `AdaptiveContext` at invocation time. Composes data from `PreferenceProvider`
(LEARN-001) and `ProfileProvider` (ADR-040) into a single adaptive view.

The Protocol is consumer-agnostic — it does not know which AI operation
consumes the data. Consumer-specific logic lives in the enricher or service.

Split out of ``contracts.py`` to stay under RULE-04's 200 LOC hard limit
(``contracts.py`` was at 160 LOC; adding the Protocol would have pushed it
to 233 LOC).

See:
    ADR-069 (Adaptive Context + Dialogue Coach Vertical),
    CONSTRAINTS.md RULE-03 (Contracts first), RULE-04 (Modularise).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from narrare_core.ai_invocation.adaptive_context import (
        AdaptiveContext,
        AdaptiveSettings,
    )


@runtime_checkable
class AdaptiveContextProvider(Protocol):
    """Assembles an `AdaptiveContext` for an AI invocation.

    Implementations compose data from:
    - `PreferenceProfile` (LEARN-001 / ADR-033 / mem0)
    - `ProjectWritingProfile` (ADR-040; contains CharacterVoiceProfiles)
    - `AdaptiveSettings` (User-Settings)

    The Provider is **consumer-agnostic** — it does not know which AI operation
    consumes the data. Consumer-specific logic (e.g. Voice-Fidelity-Scoring
    for Dialogue Coach) belongs in the respective service or agent.

    Implementations MAY perform I/O (mem0, DB) and SHOULD degrade gracefully
    (ADR-038 D7): on missing data, return an `AdaptiveContext` with empty
    strings but correct IDs.

    The ``@runtime_checkable`` decorator enables ``isinstance`` checks against
    this Protocol (used by conformance tests). It performs structural
    duck-typing (attributes present) — it does NOT verify signatures.

    See:
        ADR-069.
    """

    async def get_context(
        self,
        user_id: object,
        project_id: object,
    ) -> AdaptiveContext:
        """Return the consolidated `AdaptiveContext` for user+project.

        Args:
            user_id: The user identifier.
            project_id: The project identifier.

        Returns:
            An `AdaptiveContext`. Even if no preferences or voice profiles
            exist, a valid object with empty fields is returned (graceful
            degradation per ADR-038 D7).
        """
        ...

    async def get_settings(
        self,
        user_id: object,
        project_id: object,
    ) -> AdaptiveSettings:
        """Load the persisted `AdaptiveSettings` for user+project.

        Returns:
            The stored settings, or default settings if none are stored.
        """
        ...
