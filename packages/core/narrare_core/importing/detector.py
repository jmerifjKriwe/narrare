# packages/core/narrare_core/importing/detector.py
"""Chapter detection — deterministic, pure orchestration (ADR-091).

Same (filename, text) always yields the same chapter list: the stateless
preview/commit pair relies on this (re-parse contract, spec §4.2).
"""

from __future__ import annotations

from narrare_core.importing.models import (
    CHAPTER_STATUSES,
    TITLE_MAX_LENGTH,
    DetectedChapter,
)
from narrare_core.importing.splitting import (
    fallback_title,
    split_markdown_sections,
    split_marker_sections,
)
from narrare_core.shared.frontmatter import parse_frontmatter


def detect_chapters(filename: str, text: str) -> list[DetectedChapter]:
    """Detect chapters in one uploaded file's decoded text.

    Extension dispatch is case-insensitive (.md/.txt); anything else yields
    [] — extension guardrails are the API layer's job (spec §4.1).
    """
    lowered = filename.lower()
    if lowered.endswith(".md"):
        return _detect_markdown(filename, text)
    if lowered.endswith(".txt"):
        return _detect_txt(filename, text)
    return []


def _count_words(content: str) -> int:
    """Mirror of DemoLoader / chapters.repository.count_words."""
    return len(content.split()) if content.strip() else 0


def _clamp_title(title: str) -> str:
    """Clamp to the Chapter.title column limit (visible — preview shows it)."""
    return title[:TITLE_MAX_LENGTH]


def _detect_markdown(filename: str, text: str) -> list[DetectedChapter]:
    parsed = parse_frontmatter(text)
    fm_title = str(parsed.get("title", "")).strip() or None
    raw_status = parsed.get("status")
    status = (
        raw_status if isinstance(raw_status, str) and raw_status in CHAPTER_STATUSES else "draft"
    )

    chapters: list[DetectedChapter] = []
    for heading, body in split_markdown_sections(parsed.content):
        if not body.strip():
            continue
        title = heading if heading else (fm_title or fallback_title(filename))
        chapters.append(
            DetectedChapter(
                title=_clamp_title(title),
                content=body,
                word_count=_count_words(body),
                status=status,
                source_file=filename,
            )
        )
    return chapters


def _detect_txt(filename: str, text: str) -> list[DetectedChapter]:
    chapters: list[DetectedChapter] = []
    for marker, body in split_marker_sections(text):
        if not body.strip():
            continue
        title = marker if marker else fallback_title(filename)
        chapters.append(
            DetectedChapter(
                title=_clamp_title(title),
                content=body,
                word_count=_count_words(body),
                status="draft",
                source_file=filename,
            )
        )
    return chapters
