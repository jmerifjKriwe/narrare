"""TaskIQ task stubs for async event processing.

Tasks are triggered by domain events published via ``EventPublisher``.
Each task stub logs the event and performs the actual work (mem0 calls,
agent invocations) in the background.

TaskIQ integration will be completed in a future iteration. These stubs
provide the interface and logging so event flow can be tested end-to-end.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from narrare.events.feedback_events import FeedbackRecorded, PreferenceAnalysisTriggered

logger = structlog.get_logger(__name__)


async def process_feedback_memory(event: FeedbackRecorded) -> None:
    """Process a FeedbackRecorded event by forwarding to mem0.

    This task is triggered when a feedback event is recorded. It
    calls ``mem0.add()`` with the translated memory text so
    preferences can be extracted semantically.

    TaskIQ integration: This will become a ``@taskiq_task`` decorated
    function that runs on a worker process.

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


async def run_preference_analysis(event: PreferenceAnalysisTriggered) -> None:
    """Run preference analysis for a user/project pair.

    This task is triggered when enough feedback events accumulate.
    It calls ``PreferenceAnalysisService.analyze()`` to run the
    PreferenceAnalysisAgent and persist the results.

    TaskIQ integration: This will become a ``@taskiq_task`` decorated
    function that runs on a worker process.

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
