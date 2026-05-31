"""Shared helper factories for CoAuthorApplyService tests.

Extracted per RULE-04 (file size limit) to avoid duplication
across split test files.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

# pyright: reportUnusedFunction=false
# Functions are imported by test_coauthor_apply_service.py and
# test_coauthor_feedback_service.py — pyright's per-file scan does
# not track cross-file usage for _-prefixed module-level functions.


def _make_chapter(**overrides: Any) -> Any:
    """Create a Chapter model instance with sensible defaults."""
    from narrare.chapters.models import Chapter

    chapter = Chapter()
    defaults: dict[str, Any] = {
        "id": uuid4(),
        "novel_id": uuid4(),
        "title": "Test Chapter",
        "content": "The original chapter content. It was quite good.",
        "position": 0,
        "word_count": 9,
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        setattr(chapter, key, value)
    return chapter


def _make_generation_request(**overrides: Any) -> Any:
    """Create a GenerationRequest model instance with sensible defaults."""
    from narrare.writing.models import GenerationRequest

    req = GenerationRequest()
    defaults: dict[str, Any] = {
        "id": uuid4(),
        "chapter_id": uuid4(),
        "novel_id": uuid4(),
        "user_id": uuid4(),
        "mode": "co_author",
        "status": "completed",
        "tone": "balanced",
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        setattr(req, key, value)
    return req


def _apply_request(*, with_rejected: bool = False, **overrides: Any) -> Any:
    """Create an ApplyChangesRequest with sensible defaults."""
    from narrare.writing.schemas_coauthor import ApplyChangesRequest, TextChange

    defaults: dict[str, Any] = {
        "request_id": uuid4(),
        "original": "The original chapter content. It was quite good.",
        "accepted": [
            TextChange(
                original_text="quite good",
                revised_text="excellent",
            ),
        ],
        "rejected": [],
    }
    if with_rejected:
        defaults["rejected"] = [
            TextChange(
                original_text="original",
                revised_text="first",
            ),
        ]
    defaults.update(overrides)
    return ApplyChangesRequest(**defaults)
