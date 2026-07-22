"""Map DialogueCoachOutput → API response schemas.

Extracted from ``service.py`` for RULE-04 compliance. Owns the single
responsibility of translating Core agent output types into the Backend
API response models.

See:
    ADR-069 Decision 9 (before/after blocks, not char-level diff),
    RULE-04 (Modularise, never compress).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.ai_assist.schemas import (
    DialogueAlternativeResponse,
    DialogueCoachMode,
    DialogueCoachResponse,
    DialogueIssueResponse,
)

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.agents.dialogue_coach_types import DialogueCoachOutput


def map_output_to_response(
    *,
    chapter_id: UUID,
    mode: DialogueCoachMode,
    output: DialogueCoachOutput,
) -> DialogueCoachResponse:
    """Translate the Core DialogueCoachOutput into the API response schema."""
    issues = [
        DialogueIssueResponse(
            issue_type=i.issue_type,
            speaker=i.speaker,
            original_quote=i.original_quote,
            diagnosis=i.diagnosis,
            severity=i.severity,
            alternatives=[
                DialogueAlternativeResponse(rewrite=a.rewrite, explanation=a.explanation)
                for a in (i.alternatives or [])
            ]
            if i.alternatives is not None
            else None,
        )
        for i in output.issues
    ]
    return DialogueCoachResponse(
        chapter_id=str(chapter_id),
        mode=mode,
        issues=issues,
        adaptive_summary=output.adaptive_summary,
    )
