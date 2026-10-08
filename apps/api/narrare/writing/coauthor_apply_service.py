"""Co-author apply service — apply changes and record feedback.

Separate service class per RULE-04: :class:`CoAuthorService` handles
streaming; this class handles post-stream operations (apply + feedback).

Each method is self-contained and stateless from the frontend's
perspective — only ``original`` + ``accepted`` text segments are needed.

Implements the ``apply_changes`` and ``record_feedback`` methods from
:class:`CoAuthorServiceProtocol` (``contracts_coauthor.py``, RULE-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.writing._helpers import get_validated_request, record_batch_feedback
from narrare_core.shared.errors import NotFoundError
from narrare_core.writing.text_reconstructor import reconstruct_text

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.analytics.writing_stats_recorder import WritingStatsRecorder
    from narrare.chapters.models import Chapter
    from narrare.chapters.repository import ChapterRepository
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.schemas_coauthor import ApplyChangesRequest
    from narrare_core.memory.protocols import FeedbackCollector

from narrare.writing.schemas_coauthor import ChangeFeedback

logger = structlog.get_logger(__name__)


class CoAuthorApplyService:
    """Post-stream co-author operations: apply changes, record feedback.

    Lightweight service — no pipeline, no model config.  Only needs
    repositories and an optional feedback collector.

    Dependencies are injected via constructor (DI pattern, RULE-07).
    """

    def __init__(
        self,
        repo: GenerationRepository,
        chapter_repo: ChapterRepository,
        feedback_service: FeedbackCollector | None = None,
        writing_stats_recorder: WritingStatsRecorder | None = None,
    ) -> None:
        self._repo = repo
        self._chapter_repo = chapter_repo
        self._feedback = feedback_service
        self._writing_stats_recorder = writing_stats_recorder

    # -- Public API ------------------------------------------------------------

    async def apply_changes(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        user_id: str,
        request: ApplyChangesRequest,
    ) -> Chapter:
        """Apply accepted co-author changes to chapter content.

        Uses :func:`~narrare_core.writing.text_reconstructor.reconstruct_text`
        to rebuild the chapter text from original + accepted changes.
        Persists via ChapterRepository and records feedback for rejected
        changes via the FeedbackCollector.

        Args:
            chapter_id: Chapter to apply changes to.
            novel_id: Novel the chapter belongs to.
            user_id: Authenticated user identifier.
            request: Original text + accepted/rejected changes.

        Returns:
            Updated Chapter ORM model.

        Raises:
            NotFoundError: If the generation request does not exist or
                belongs to another user, if the request row does not
                reference the addressed chapter and novel, or if the
                chapter does not exist.
        """
        # Ownership gate (Pattern A): the write is bound to a generation
        # request the caller owns — unknown and foreign request ids are
        # indistinguishable (anti-enumeration).
        request_model = await get_validated_request(self._repo, request.request_id, user_id)
        if request_model.chapter_id != chapter_id or request_model.novel_id != novel_id:
            raise NotFoundError("Chapter", identifier=str(chapter_id))

        chapter = await self._chapter_repo.get_by_id(chapter_id, novel_id)
        if not chapter:
            raise NotFoundError("Chapter", identifier=str(chapter_id))

        # Rekonstruktion (reine Funktion — kein I/O)
        accepted_dicts = [
            {"original_text": c.original_text, "revised_text": c.revised_text}
            for c in request.accepted
        ]
        reconstructed = reconstruct_text(request.original, accepted_dicts)
        word_count = len(reconstructed.split())
        # Capture BEFORE the repo write — repositories update the chapter
        # row in place, so the old word count is unrecoverable afterwards
        # (same hazard the E3a editor write guards against).
        old_word_count = chapter.word_count
        updated = await self._chapter_repo.update_content(
            chapter,
            reconstructed,
            word_count,
        )

        # STATS-001 (ADR-095): signed word-count delta for this apply write.
        # The recorder is never-raises and skips zero deltas internally — no
        # try/except here by contract. The recorded user id is the UUID on
        # the gate-validated request row (== caller, proven by Pattern A).
        if self._writing_stats_recorder is not None:
            await self._writing_stats_recorder.record_delta(
                user_id=request_model.user_id,
                novel_id=novel_id,
                chapter_id=chapter_id,
                delta_words=word_count - old_word_count,
            )

        # Feedback for rejected changes (LEARN-001) — recorded against the
        # caller-validated request row (never another user's learning data).
        if request.rejected and self._feedback:
            rejected_fb = [
                ChangeFeedback(
                    change_id=f"rejected_{i}",
                    action="reject",
                    focus="word_choice",
                    original=c.original_text,
                    revised=c.revised_text,
                )
                for i, c in enumerate(request.rejected)
            ]
            await record_batch_feedback(
                self._feedback,
                request_model,
                rejected_fb,
            )

        return updated

    async def record_feedback(
        self,
        request_id: UUID,
        feedback: list[ChangeFeedback],
        user_id: str,
    ) -> None:
        """Record batch per-change feedback for co-author (LEARN-001).

        Creates individual ``FeedbackEvent`` entries for each change
        feedback item.  Silently no-ops when no ``FeedbackCollector``
        is configured.  The ownership gate (Pattern A) guarantees the
        events are stamped with the caller's own user id — feedback can
        never pollute another user's preference learning.

        Args:
            request_id: The generation request ID these changes belong to.
            feedback: Per-change feedback items.
            user_id: Authenticated user identifier (access check).

        Raises:
            NotFoundError: If the generation request does not exist or
                belongs to another user.
        """
        request_model = await get_validated_request(self._repo, request_id, user_id)
        await record_batch_feedback(self._feedback, request_model, feedback)
