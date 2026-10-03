"""Bulk extraction wire schemas (F2, ADR-092, spec §4).

Pydantic request/response models for the bulk extraction job surface
(``POST/GET …/kb/extract/bulk…``). Field names and shapes are the spec §4
contract; every model forbids extra fields so FE/BE drift fails loudly at
the seam (RULE-17 mirror target). Item counts live in the status view;
full ``ExtractionOutput`` payloads appear only in the results view
(payload-size boundary, spec §4.2/§4.3).
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — needed at runtime for Pydantic model resolution
from enum import StrEnum
from typing import Self
from uuid import UUID  # noqa: TC003 — needed at runtime for Pydantic model resolution

from pydantic import BaseModel, ConfigDict, Field, model_validator

from narrare.kb.bulk_extraction.contracts import BULK_EXTRACT_MAX_CHAPTERS
from narrare_core.agents.extraction_types import (
    ExtractionOutput,  # noqa: TC001 — runtime Pydantic resolution
)


class BulkChapterState(StrEnum):
    """Per-chapter state inside a bulk job (spec §4.2 — normative set)."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class BulkJobStatus(StrEnum):
    """Job-level lifecycle status (spec §4.1 — normative set)."""

    PENDING = "pending"
    RUNNING = "running"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class BulkExtractionStartRequest(BaseModel):
    """Request body for the bulk start endpoint (spec §4.1)."""

    model_config = ConfigDict(extra="forbid")

    chapter_ids: list[UUID] = Field(min_length=1, max_length=BULK_EXTRACT_MAX_CHAPTERS)
    """Explicit chapters to process (``ImportCommitResponse.chapters`` ids);
    1..200 items, duplicates/foreign ids → 422 naming the offending id."""


class BulkExtractionTotals(BaseModel):
    """Aggregated per-state counts for one job (spec §4.1/§4.2)."""

    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    """All chapters in the job."""

    done: int = Field(ge=0)
    """Chapters whose extraction finished successfully."""

    failed: int = Field(ge=0)
    """Chapters whose extraction raised (job continues per chapter)."""

    remaining: int = Field(ge=0)
    """Pending + running counts (spec §4.2)."""


class BulkChapterStatusView(BaseModel):
    """One chapter in the status poll response (spec §4.2)."""

    model_config = ConfigDict(extra="forbid")

    chapter_id: UUID
    """Chapter the row describes."""

    title: str
    """Chapter title at job-creation time."""

    position: int = Field(ge=0)
    """Chapter position — the job's canonical (server-sorted) order."""

    state: BulkChapterState
    """Per-chapter state (normative set)."""

    item_count: int | None = None
    """Extracted item count — set (≥ 0) iff ``state = done``, else ``None``."""

    error: str | None = None
    """Chapter-level failure reason — set iff ``state = failed`` (spec §5/§9)."""

    @model_validator(mode="after")
    def _item_count_iff_done(self) -> Self:
        """Self-defending invariant: ``item_count`` present ⟺ ``state = done``."""
        if (self.state is BulkChapterState.DONE) != (self.item_count is not None):
            raise ValueError("item_count must be set if and only if state is 'done'")
        return self


class BulkExtractionJobView(BaseModel):
    """Job summary returned by start/cancel/resume (spec §4.1/§4.4/§4.5)."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    """Opaque job id (``token_urlsafe(16)``); foreign ≡ unknown → 404."""

    novel_id: UUID
    """Novel the job belongs to (routes are novel-scoped)."""

    status: BulkJobStatus
    """Job lifecycle status (normative set)."""

    created_at: datetime
    """Job creation timestamp (UTC)."""

    updated_at: datetime
    """Last state-transition timestamp (UTC)."""

    totals: BulkExtractionTotals
    """Aggregated per-state counts."""

    error: str | None = None
    """Job-level failure reason (set iff ``status = failed``); chapter-level
    failures live in the status view's chapter rows."""


class BulkExtractionStatusView(BulkExtractionJobView):
    """Status poll response: the job view plus per-chapter rows (spec §4.2)."""

    model_config = ConfigDict(extra="forbid")

    chapters: list[BulkChapterStatusView]
    """Every job chapter in position order with its state + item count."""


class BulkExtractionResultChapter(BaseModel):
    """One chapter in the results response (spec §4.3)."""

    model_config = ConfigDict(extra="forbid")

    chapter_id: UUID
    """Chapter the row describes."""

    title: str
    """Chapter title at job-creation time."""

    position: int = Field(ge=0)
    """Chapter position — the job's canonical (server-sorted) order."""

    state: BulkChapterState
    """Per-chapter state (normative set)."""

    output: ExtractionOutput | None = None
    """Full extraction output — present iff ``state = done``, else ``None``;
    partial results of a cancelled job stay readable (resume baseline)."""

    @model_validator(mode="after")
    def _output_iff_done(self) -> Self:
        """Self-defending invariant: ``output`` present ⟺ ``state = done``."""
        if (self.state is BulkChapterState.DONE) != (self.output is not None):
            raise ValueError("output must be present if and only if state is 'done'")
        return self


class BulkExtractionResultsView(BaseModel):
    """Full outputs response (spec §4.3) — review payload for the FE panel."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    """Opaque job id; foreign ≡ unknown → 404."""

    novel_id: UUID
    """Novel the job belongs to."""

    status: BulkJobStatus
    """Job lifecycle status — outputs are readable in any job state."""

    chapters: list[BulkExtractionResultChapter]
    """Every job chapter in position order; done chapters carry ``output``."""


__all__ = [
    "BulkChapterState",
    "BulkChapterStatusView",
    "BulkExtractionJobView",
    "BulkExtractionResultChapter",
    "BulkExtractionResultsView",
    "BulkExtractionStartRequest",
    "BulkExtractionStatusView",
    "BulkExtractionTotals",
    "BulkJobStatus",
]
