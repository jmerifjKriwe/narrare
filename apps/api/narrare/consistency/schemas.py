"""Consistency request/response Pydantic models.

Request/Response schemas for CONS-001 (Consistency Checker).
Domain types (``ConsistencyIssue``, enums) are imported directly from
core types — no duplication of Pydantic models across layers.

See:
    :mod:`narrare_core.agents.consistency_types` — Core domain types.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from narrare_core.agents.consistency_types import (
    ConsistencyCheckType,
    ConsistencyIssue,
    ConsistencySeverity,
)


class ConsistencyRequest(BaseModel):
    """Request to run consistency check.

    Attributes:
        chapter_ids: Chapters to check. If empty, checks all chapters.
        check_types: Which types to check. If empty, runs all.
        include_kb: Whether to include KB data for context. Default True.
    """

    chapter_ids: list[UUID] = Field(default_factory=list[UUID])
    check_types: list[ConsistencyCheckType] = Field(default_factory=list[ConsistencyCheckType])
    include_kb: bool = True


class ConsistencyResponse(BaseModel):
    """Response from consistency check.

    Attributes:
        novel_id: The novel that was checked.
        chapter_ids: Which chapters were analyzed.
        check_types: Which checks were executed.
        issues: All issues found, grouped by severity.
        error_count: Number of ERROR severity issues.
        warning_count: Number of WARNING severity issues.
        info_count: Number of INFO severity issues.
        total_issues: Total number of issues found.
        overall_assessment: Summary of project consistency health.
        analyzed_at: ISO datetime when the check was performed.
    """

    novel_id: UUID
    chapter_ids: list[UUID]
    check_types: list[ConsistencyCheckType]
    issues: list[ConsistencyIssue]
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    total_issues: int = 0
    overall_assessment: str = ""
    analyzed_at: str = ""

    def model_post_init(self, __context: object) -> None:
        """Auto-compute severity counts after initialization."""
        self.error_count = sum(1 for i in self.issues if i.severity == ConsistencySeverity.ERROR)
        self.warning_count = sum(
            1 for i in self.issues if i.severity == ConsistencySeverity.WARNING
        )
        self.info_count = sum(1 for i in self.issues if i.severity == ConsistencySeverity.INFO)
        self.total_issues = len(self.issues)
