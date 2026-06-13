"""SSE stage event schemas for staged consistency pipeline (ADR-044).

Defines the ``ConsistencyStageEvent`` model for streaming progressive
results during the two-stage consistency check (extraction → analysis).

Extracted from ``schemas.py`` per RULE-04 to keep schemas focused on
REST request/response models.

See:
    :mod:`narrare.consistency.schemas` — REST request/response models.
    ADR-044 — Staged Multi-Agent Consistency Pipeline.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Pydantic resolves this nested model at runtime.
from narrare_core.agents.consistency_types import ConsistencyIssue  # noqa: TC001


class ConsistencyStageEvent(BaseModel):
    """SSE event for staged pipeline progress (ADR-044 Slice 4).

    Streamed during ``POST /consistency/check/stream`` to provide
    stage-by-stage progress to the frontend.

    Attributes:
        stage: Which stage is currently running.
        status: Stage event status (start, progress, issue, complete).
        progress: Progress within the current stage (0.0-1.0).
        message: Human-readable progress description.
        facts_extracted: Number of facts extracted (populated after stage 1).
        issues_found: Number of issues found so far (populated during stage 2).
        issue: A single issue emitted progressively during consistency checking.
    """

    stage: Literal[
        "extracting_facts",
        "checking_consistency",
        "complete",
    ]
    status: Literal["start", "progress", "issue", "complete"] = "progress"
    progress: float = Field(ge=0.0, le=1.0, default=0.0)
    message: str = ""
    facts_extracted: int | None = None
    issues_found: int | None = None
    issue: ConsistencyIssue | None = None
