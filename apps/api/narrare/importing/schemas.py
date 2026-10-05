"""Import module Pydantic schemas (request/response) — RULE-17 mirror of
packages/web/types/importing.ts.

Vocabulary v2 (ADR-091 Amendment 2): ``splits``/``merges`` address
ORIGINAL detected indices; ``excluded_indices``/``title_overrides``
address FINAL (post-ops) indices. ``extra="forbid"`` makes unknown
fields a loud 422 instead of a silent drop (version-skew defense).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from narrare_core.importing import SPLIT_CANDIDATES_MAX


class ImportSplitCandidate(BaseModel):
    """One `###`+ subheading offered as a split point (capped, ≤ 200)."""

    ordinal: int = Field(ge=0)
    heading: str = Field(min_length=1, max_length=500)
    words_before: int = Field(ge=0)


class ImportSplitOperation(BaseModel):
    """Split chapter ``index`` at the given candidate ordinals."""

    index: int = Field(ge=0)
    at: list[int] = Field(min_length=1)


class ImportMergeOperation(BaseModel):
    """Merge a contiguous ascending run of original chapters (≥ 2)."""

    indices: list[int] = Field(min_length=2)


class ImportPreviewItem(BaseModel):
    """One detected chapter in a preview (index = ORIGINAL space key)."""

    index: int = Field(ge=0)
    suggested_title: str = Field(min_length=1, max_length=500)
    word_count: int = Field(ge=0)
    source_file: str
    split_candidates: list[ImportSplitCandidate] = Field(default_factory=list[ImportSplitCandidate])


class ImportPreviewResponse(BaseModel):
    items: list[ImportPreviewItem]
    file_count: int = Field(ge=1)
    chapter_count: int = Field(ge=1)
    total_word_count: int = Field(ge=0)


class ImportCommitAdjustments(BaseModel):
    """User edits applied on top of the deterministic re-parse (v2)."""

    model_config = ConfigDict(extra="forbid")

    # Op-list cap = SPLIT_CANDIDATES_MAX (200): bounds DoS surface at the same
    # scale as the offered split points / BULK_EXTRACT_MAX_CHAPTERS.
    splits: list[ImportSplitOperation] = Field(
        default_factory=list[ImportSplitOperation], max_length=SPLIT_CANDIDATES_MAX
    )
    merges: list[ImportMergeOperation] = Field(
        default_factory=list[ImportMergeOperation], max_length=SPLIT_CANDIDATES_MAX
    )
    excluded_indices: list[int] = Field(default_factory=list[int])  # FINAL space
    title_overrides: dict[str, str] = Field(default_factory=dict)  # FINAL space


class ImportCommitChapterInfo(BaseModel):
    id: str
    title: str
    position: int
    word_count: int


class ImportCommitResponse(BaseModel):
    novel_id: str
    created_count: int = Field(ge=1)
    first_position: int = Field(ge=0)
    last_position: int = Field(ge=0)
    chapters: list[ImportCommitChapterInfo]
