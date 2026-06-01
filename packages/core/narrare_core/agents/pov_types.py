"""Output types for POVDetectionAgent.

See ADR-015 Phase 2.1 — Output Types.
ANAL-004 — POV Analysis (LLM-based).
"""

from __future__ import annotations

from pydantic import BaseModel


class POVDetectedScene(BaseModel):
    """A scene with its detected POV character.

    Attributes:
        scene_index: 0-based index of the scene within the text.
        pov_character: Name of the detected POV character.
        confidence: Confidence score for the POV assignment (0.0-1.0).
        text_sample: First ~100 characters of the scene for reference.
    """

    scene_index: int = 0
    pov_character: str = ""
    confidence: float = 0.0
    text_sample: str = ""


class POVDetectedIssue(BaseModel):
    """A POV violation detected in the text.

    Attributes:
        type: Category of the violation (``"head_hop"``,
            ``"knowledge_leak"``, ``"emotional_leak"``,
            ``"physical_impossibility"``).
        location: Chapter / paragraph / line reference.
        text: The problematic text snippet.
        explanation: Why this is a violation.
        suggestion: How to fix it.
        severity: ``"error"`` (definite violation) or ``"warning"``
            (potential issue).
    """

    type: str = ""
    location: str = ""
    text: str = ""
    explanation: str = ""
    suggestion: str = ""
    severity: str = "warning"


class POVDetectionOutput(BaseModel):
    """Structured output from the POVDetectionAgent.

    Attributes:
        scenes: Per-scene POV character assignments.
        issues: Flagged POV violations.
        pov_distribution: Character name -> proportion of text (0.0-1.0).
        switch_count: Total number of POV switches detected.
        analysis_type: Detected POV type (``"third_limited"``,
            ``"first_person"``, ``"omniscient"``, ``"mixed"``).
        overall_assessment: Free-text summary of POV consistency.
    """

    scenes: list[POVDetectedScene] = []
    issues: list[POVDetectedIssue] = []
    pov_distribution: dict[str, float] = {}
    switch_count: int = 0
    analysis_type: str = ""
    overall_assessment: str = ""
