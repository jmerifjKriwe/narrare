"""Import module Pydantic schemas (request/response) — RULE-17 mirror of
packages/web/types/importing.ts (added in the frontend client task)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ImportPreviewItem(BaseModel):
    """One detected chapter in a preview (index = commit adjustment key)."""

    index: int = Field(ge=0)
    suggested_title: str = Field(min_length=1, max_length=500)
    word_count: int = Field(ge=0)
    source_file: str


class ImportPreviewResponse(BaseModel):
    items: list[ImportPreviewItem]
    file_count: int = Field(ge=1)
    chapter_count: int = Field(ge=1)
    total_word_count: int = Field(ge=0)


class ImportCommitAdjustments(BaseModel):
    """User edits applied on top of the deterministic re-parse."""

    excluded_indices: list[int] = Field(default_factory=list[int])
    title_overrides: dict[str, str] = Field(default_factory=dict)


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
