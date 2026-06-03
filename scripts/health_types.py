"""Shared types and constants for system health scoring.

Extracted to avoid circular imports between check_system_health.py and health_format.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field

HEALTHY_THRESHOLD = 0.85
DEGRADED_THRESHOLD = 0.70


@dataclass
class GateResult:
    """Score contribution from one gate."""

    name: str
    weight: float
    score: float
    details: str = ""


@dataclass
class HealthReport:
    """Aggregated system health report."""

    score: float
    status: str
    gates: list[GateResult] = field(default_factory=list[GateResult])

    @property
    def exit_code(self) -> int:
        return 1 if self.score < DEGRADED_THRESHOLD else 0
