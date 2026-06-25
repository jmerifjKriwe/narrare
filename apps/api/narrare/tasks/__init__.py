"""TaskIQ task registry for async event processing.

This package owns the shared :data:`broker` (see :mod:`narrare.tasks.broker`).
Importing this package registers every background task on the broker, so the
taskiq worker target ``narrare.tasks.broker:broker`` discovers all tasks —
importing a submodule always imports the parent package first, which runs
this file.

Tasks:
- Feedback / preference memory (mem0) — stubs, wired for future implementation.
- Embedding generation — see :mod:`narrare.embeddings.tasks`.
- Wiki summary generation — see :mod:`narrare.wiki.tasks`.
"""

from __future__ import annotations

import structlog

import narrare.embeddings.tasks as _embeddings_tasks_module
import narrare.wiki.tasks as _wiki_tasks_module

# Runtime import (not TYPE_CHECKING): taskiq's @broker.task resolves type hints
# at decoration time via get_type_hints(), so FeedbackRecorded must be present.
from narrare.events.feedback_events import (  # noqa: TC001
    FeedbackRecorded,
    PreferenceAnalysisTriggered,
)
from narrare.tasks.broker import broker

_TASK_MODULES = (_embeddings_tasks_module, _wiki_tasks_module)
"""Task modules whose import registers tasks on :data:`broker`."""

logger = structlog.get_logger(__name__)


@broker.task(task_name="process_feedback_memory", max_retries=3)
async def process_feedback_memory(event: FeedbackRecorded) -> None:
    """Process a FeedbackRecorded event by forwarding to mem0.

    This task is triggered when a feedback event is recorded. It
    calls ``mem0.add()`` with the translated memory text so
    preferences can be extracted semantically.

    Args:
        event: The FeedbackRecorded domain event.
    """
    logger.info(
        "task_process_feedback_memory",
        user_id=str(event.user_id),
        project_id=str(event.project_id),
        event_id=str(event.event_id),
        status="stub",
    )
    # TODO (Phase 7): Implement actual mem0.add() call
    # 1. Load FeedbackEvent from DB
    # 2. Translate to memory text via FeedbackService._translate_to_memory_text
    # 3. Call mem0.add() with user/project context


@broker.task(task_name="run_preference_analysis", max_retries=3)
async def run_preference_analysis(event: PreferenceAnalysisTriggered) -> None:
    """Run preference analysis for a user/project pair.

    This task is triggered when enough feedback events accumulate.
    It calls ``PreferenceAnalysisService.analyze()`` to run the
    PreferenceAnalysisAgent and persist the results.

    Args:
        event: The PreferenceAnalysisTriggered domain event.
    """
    logger.info(
        "task_run_preference_analysis",
        user_id=str(event.user_id),
        project_id=str(event.project_id),
        event_count=event.event_count,
        status="stub",
    )
    # TODO (Phase 7): Implement actual analysis call
    # 1. Create PreferenceAnalysisService with DI
    # 2. Call service.analyze(user_id, project_id)
    # 3. Log results
