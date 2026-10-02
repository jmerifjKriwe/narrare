# packages/core/narrare_core/importing/models.py
"""Data shapes for chapter detection (SETUP-003 v1 — pure, I/O-free)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

#: Chapter statuses v1 can produce (Chapter.status is String(20)).
CHAPTER_STATUSES: frozenset[str] = frozenset({"draft", "reviewed", "final"})

#: Chapter.title column limit — titles are clamped here so the preview the
#: user sees is storable as-is (user edits can still shorten).
TITLE_MAX_LENGTH: Final[int] = 500


@dataclass(frozen=True, slots=True)
class DetectedChapter:
    """One chapter detected in an uploaded file (deterministic parse result)."""

    title: str
    content: str
    word_count: int
    status: str
    source_file: str
