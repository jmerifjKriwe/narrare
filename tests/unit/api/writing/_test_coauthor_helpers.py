"""Shared helper factories for CoAuthorApplyService tests.

Extracted per RULE-04 (file size limit) to avoid duplication
across split test files — including the IDOR ownership matrix files
(``test_coauthor_apply_ownership*.py``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from narrare.chapters.repository import ChapterRepository
    from narrare.writing.repository import GenerationRepository
    from narrare_core.memory.protocols import FeedbackCollector

# pyright: reportUnusedFunction=false
# Functions are imported by test_coauthor_apply_service.py,
# test_coauthor_feedback_service.py and the ownership matrix files —
# pyright's per-file scan does not track cross-file usage for
# _-prefixed module-level functions.


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


# -- Ownership-matrix builders (IDOR remediation plan S2) --------------------


def _gen_repo(
    *,
    owner: UUID,
    chapter_id: UUID | None = None,
    novel_id: UUID | None = None,
) -> tuple[MagicMock, Any]:
    """Mock GenerationRepository resolving to ``owner``'s request row."""
    gen_req = _make_generation_request(
        chapter_id=chapter_id or uuid4(),
        novel_id=novel_id or uuid4(),
        user_id=owner,
    )
    repo = MagicMock(spec=["get_by_id"])
    repo.get_by_id = AsyncMock(return_value=gen_req)
    return repo, gen_req


def _empty_gen_repo() -> MagicMock:
    """Mock GenerationRepository resolving nothing (unknown request id)."""
    repo = MagicMock(spec=["get_by_id"])
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


def _chapter_repo_mock(chapter: Any) -> MagicMock:
    """Mock ChapterRepository: loads ``chapter``, records update calls."""
    chapter_repo = MagicMock(spec=["get_by_id", "update_content"])
    chapter_repo.get_by_id = AsyncMock(return_value=chapter)

    async def _update(c: Any, content: str, wc: int) -> Any:
        c.content = content
        c.word_count = wc
        return c

    chapter_repo.update_content = AsyncMock(side_effect=_update)
    return chapter_repo


def _feedback_collector_mock() -> MagicMock:
    """Mock FeedbackCollector recording every event for later inspection."""
    feedback = MagicMock(spec=["record"])
    feedback.record = AsyncMock()
    return feedback


def _apply_service(
    repo: MagicMock,
    chapter_repo: MagicMock | None = None,
    feedback: MagicMock | None = None,
) -> Any:
    """CoAuthorApplyService over the given mock repositories."""
    from narrare.writing.coauthor_apply_service import CoAuthorApplyService

    return CoAuthorApplyService(
        repo=cast("GenerationRepository", repo),
        chapter_repo=cast(
            "ChapterRepository", chapter_repo or MagicMock(spec=["get_by_id", "update_content"])
        ),
        feedback_service=cast("FeedbackCollector", feedback) if feedback else None,
    )


def _feedback_items() -> list[Any]:
    """Single-element per-change feedback list."""
    from narrare.writing.schemas_coauthor import ChangeFeedback

    return [
        ChangeFeedback(
            change_id="ch_1",
            action="accept",
            original="old text",
            revised="new text",
        ),
    ]
