"""Typed models for staged consistency eval cases."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from narrare_core.agents.consistency_triage_types import (  # noqa: TC001 — Pydantic needs runtime model types
    TriageAssessment,
)
from narrare_core.agents.consistency_types import ConsistencyCheckType, ConsistencyIssue
from narrare_core.agents.fact_extractor_types import (  # noqa: TC001 — Pydantic needs runtime model types
    ExtractedFact,
    TimelineEventEnvelope,
)


def _empty_kb_summaries() -> list[dict[str, object]]:
    return []


def _empty_timeline_envelopes() -> list[TimelineEventEnvelope]:
    return []


def _empty_extracted_facts() -> list[ExtractedFact]:
    return []


def _empty_issues() -> list[ConsistencyIssue]:
    return []


def _default_check_types() -> list[ConsistencyCheckType]:
    return [ConsistencyCheckType.TIMELINE]


def _empty_triage_assessments() -> list[TriageAssessment]:
    return []


class StagedConsistencyInput(BaseModel):
    """Input for ADR-044 staged consistency eval cases.

    ``stage`` selects which part of the two-stage pipeline the case evaluates:
    fact extraction only, Stage 2 comparison only, or end-to-end orchestration.
    """

    stage: Literal["fact_extraction", "consistency_comparison", "end_to_end"]
    chapter_texts: dict[str, str] = Field(default_factory=dict)
    kb_entity_names: list[str] = Field(default_factory=list)
    kb_entity_summaries: list[dict[str, object]] = Field(default_factory=_empty_kb_summaries)
    timeline_envelopes: list[TimelineEventEnvelope] = Field(
        default_factory=_empty_timeline_envelopes
    )
    extracted_facts: list[ExtractedFact] = Field(default_factory=_empty_extracted_facts)
    check_types: list[ConsistencyCheckType] = Field(default_factory=_default_check_types)
    language: str = "en"
    genre: str = "Fantasy"


class StagedConsistencyResult(BaseModel):
    """Normalized output for staged consistency eval scoring.

    Triage fields (decision-pattern pilot, Task 12) are default-off and
    filled only by the runtime task when ``NARRARE_EVAL_TRIAGE_MODEL`` is
    set. ``issues`` always carries the RAW ConsistencyAgent output so
    evaluator scores stay comparable with and without the triage stage;
    ``triaged_issues`` / ``triage_assessments`` ride along in the report
    artifact for the pilot measurement (rubric vs. self-reported severity).
    """

    extracted_facts: list[ExtractedFact] = Field(default_factory=_empty_extracted_facts)
    issues: list[ConsistencyIssue] = Field(default_factory=_empty_issues)
    overall_assessment: str = ""
    triaged: bool = False
    triaged_issues: list[ConsistencyIssue] = Field(default_factory=_empty_issues)
    triage_assessments: list[TriageAssessment] = Field(default_factory=_empty_triage_assessments)
