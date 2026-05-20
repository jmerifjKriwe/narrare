"""NarrareObservability — Standard-Observability-Capability.

Wird in Phase 1 implementiert. Aktuell ein No-Op-Stub,
der importiert und registriert werden kann, ohne Fehler zu werfen.

Siehe ADR-015 Phase 1.2.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai.capabilities import AbstractCapability


@dataclass
class NarrareObservability(AbstractCapability):
    """Standard-Observability-Capability.

    Wird in Phase 1 implementiert. Aktuell ein No-Op-Stub,
    der importiert und registriert werden kann, ohne Fehler zu werfen.

    Siehe ADR-015 Phase 1.2.
    """

    pass
