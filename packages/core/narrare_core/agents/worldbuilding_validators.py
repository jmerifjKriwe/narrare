"""WorldbuildingAgent output validators — ADR-035.

Deterministic invariants enforced at the agent boundary:

Phase 1:
- gap_type should be non-empty, description non-empty
- Filter gaps with empty descriptions

Phase 2:
- category and severity from known sets
- entity_ids non-empty

Usage:
    from narrare_core.agents.worldbuilding_validators import (
        validate_worldbuilding_phase1,
        validate_worldbuilding_phase2,
    )

    validator = validate_worldbuilding_phase1
    # Register: agent._agent.output_validator(validate_worldbuilding_phase1)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai import ModelRetry

if TYPE_CHECKING:
    from pydantic_ai import RunContext

    from narrare_core.agents.worldbuilding_types import (
        WorldbuildingDeps,
        WorldbuildingPhase1Output,
        WorldbuildingPhase2Output,
    )

# Known sets for validation
VALID_CATEGORIES = frozenset(
    {
        "geography",
        "politics",
        "economics",
        "system_rules",
        "timeline",
        "character",
    }
)
VALID_SEVERITIES = frozenset({"critical", "major", "minor"})


async def validate_worldbuilding_phase1(
    ctx: RunContext[WorldbuildingDeps],
    output: WorldbuildingPhase1Output,
) -> WorldbuildingPhase1Output:
    """Validate deterministic invariants for Phase 1 output.

    ADR-035: Enforces output quality at the agent boundary.
    No side effects — deterministic validation only.

    Invariants:
    - gap_type should be non-empty, description non-empty
    - Filter gaps with empty descriptions
    """
    # Filter gaps with empty descriptions
    valid_gaps = [g for g in output.gaps if g.description.strip()]

    for g in valid_gaps:
        if not g.gap_type.strip():
            raise ModelRetry("Gap must have a non-empty gap_type")
        if not g.description.strip():
            raise ModelRetry("Gap must have a non-empty description")

    return output.model_copy(update={"gaps": valid_gaps})


async def validate_worldbuilding_phase2(
    ctx: RunContext[WorldbuildingDeps],
    output: WorldbuildingPhase2Output,
) -> WorldbuildingPhase2Output:
    """Validate deterministic invariants for Phase 2 output.

    ADR-035: Enforces output quality at the agent boundary.
    No side effects — deterministic validation only.

    Invariants:
    - category and severity from known sets
    - entity_ids non-empty
    """
    for issue in output.issues:
        if not issue.entity_ids:
            raise ModelRetry(
                f"Consistency issue '{issue.description[:50]}' must have at least one entity_id"
            )
        if issue.category not in VALID_CATEGORIES:
            raise ModelRetry(
                f"Consistency issue category '{issue.category}' is not valid — "
                f"must be one of {sorted(VALID_CATEGORIES)}"
            )
        if issue.severity not in VALID_SEVERITIES:
            raise ModelRetry(
                f"Consistency issue severity '{issue.severity}' is not valid — "
                f"must be one of {sorted(VALID_SEVERITIES)}"
            )

    return output
