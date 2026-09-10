"""POV analysis output mapping — POVDetectionOutput to POVResult.

Extracted from pov_service.py for RULE-04 compliance (< 300 lines).
Contains the static mapping logic, issue type translation table,
and deps builder.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.analysis.types import (
    POVIssue,
    POVIssueType,
    POVResult,
    POVScene,
)

if TYPE_CHECKING:
    from narrare_core.agents.pov_agent import POVDeps


# ---------------------------------------------------------------------------
# Issue type mapping table
# ---------------------------------------------------------------------------

_ISSUE_TYPE_MAP: dict[str, POVIssueType] = {
    "head_hop": POVIssueType.HEAD_HOP,
    "knowledge_leak": POVIssueType.KNOWLEDGE_LEAK,
    "emotional_leak": POVIssueType.EMOTIONAL_LEAK,
    "physical_impossibility": POVIssueType.PHYSICAL_IMPOSSIBILITY,
}


def map_issue_type(raw: str) -> POVIssueType:
    """Map an agent-returned issue type string to ``POVIssueType``.

    Falls back to ``HEAD_HOP`` for unknown values (ensures we never
    lose an issue due to mapping).

    Args:
        raw: Issue type string from the agent.

    Returns:
        Corresponding ``POVIssueType`` enum member.
    """
    return _ISSUE_TYPE_MAP.get(raw, POVIssueType.HEAD_HOP)


def map_output_to_result(output: object) -> POVResult:
    """Map ``POVDetectionOutput`` to ``POVResult``.

    Converts agent-level types to API-level types:
    - ``POVDetectedScene`` → ``POVScene``
    - ``POVDetectedIssue`` → ``POVIssue``
    - Passes through distribution, switch_count, analysis_type.

    Args:
        output: ``POVDetectionOutput`` from the agent.

    Returns:
        ``POVResult`` ready for API serialization.
    """
    from narrare_core.agents.pov_types import POVDetectionOutput

    agent_output = POVDetectionOutput.model_validate(output)

    scenes: list[POVScene] = []
    for s in agent_output.scenes:
        scenes.append(
            POVScene(
                scene_index=s.scene_index,
                start_position=0,
                end_position=0,
                pov_character=s.pov_character or None,
                confidence=s.confidence,
            )
        )

    issues: list[POVIssue] = []
    for i in agent_output.issues:
        issues.append(
            POVIssue(
                type=map_issue_type(i.type),
                location=i.location,
                text=i.text,
                explanation=i.explanation,
                suggestion=i.suggestion,
                severity=i.severity,
            )
        )

    return POVResult(
        scenes=scenes,
        issues=issues,
        pov_distribution=agent_output.pov_distribution,
        switch_count=agent_output.switch_count,
        analysis_type=agent_output.analysis_type,
    )


def build_deps(
    text: str,
    language: str,
) -> POVDeps:
    """Build ``POVDeps`` — helper to keep import out of module top-level.

    Args:
        text: Concatenated chapter content.
        language: Resolved language code.

    Returns:
        A ``POVDeps`` instance.
    """
    from narrare_core.agents.pov_agent import POVDeps

    return POVDeps(
        text=text,
        language=language,
    )
