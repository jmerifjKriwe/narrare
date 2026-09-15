"""Inline-suggest support helpers.

Extracted from ``suggest_service.py`` so the service stays within the
RULE-04 300-line service limit when the ADR-086 lazy-resolution seam
(``ensure_resolved``, L36) landed — same module convention as
``wiki/generation_support.py`` and ``generation/name_dedup.py``
(helpers split, nothing compressed).

Houses:
- soft rate limiting (non-blocking, minimum interval per chapter),
- minimal chapter-context assembly for prompt enrichment.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chapters.repository import ChapterRepository

logger = structlog.get_logger(__name__)

# Soft rate limiting: minimum interval between requests per chapter.
# Non-blocking — logs a warning but still processes the request.
_MIN_SUGGEST_INTERVAL_S: float = 0.5

# Module-level dict for in-memory rate tracking.
# Key: "{chapter_id}:{user_id}", Value: monotonic timestamp of last request.
_last_request_time: dict[str, float] = {}


def track_request(chapter_id: UUID, user_id: str) -> None:
    """Track request timing for soft rate limiting (non-blocking).

    Logs a warning if requests are coming too fast but does NOT
    reject the request.  This keeps the UX responsive during
    rapid typing while providing observability for abuse detection.
    """
    now = time.monotonic()
    key = f"{chapter_id}:{user_id}"
    last = _last_request_time.get(key, 0.0)
    if last and (now - last) < _MIN_SUGGEST_INTERVAL_S:
        logger.debug(
            "suggest_rate_throttled",
            chapter_id=str(chapter_id),
            elapsed_ms=round((now - last) * 1000),
        )
    _last_request_time[key] = now


async def build_chapter_context(chapter_repo: ChapterRepository, chapter_id: UUID) -> str:
    """Assemble minimal chapter context for prompt enrichment.

    Returns a short string with chapter title and POV (if set).
    Intentionally minimal — the full ContextAssembler is too slow
    for the <500ms latency target of inline suggestions.
    """
    chapter = await chapter_repo.get(chapter_id)
    if chapter is None:
        return ""

    parts: list[str] = []
    if chapter.title:
        parts.append(f"Chapter: {chapter.title}")
    if chapter.pov_character_id:
        parts.append(f"POV: {chapter.pov_character_id}")
    return "\n".join(parts)
