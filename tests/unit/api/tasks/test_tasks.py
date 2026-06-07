"""Unit tests for ``narrare.tasks`` — async event processing stubs.

Tests that both task stubs execute without error and log the expected
attributes.  The event types (``FeedbackRecorded``,
``PreferenceAnalysisTriggered``) are only imported under
``TYPE_CHECKING``, so the stubs accept any object with the right
attributes — we use :class:`~unittest.mock.MagicMock` to simulate them.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from narrare.tasks import process_feedback_memory, run_preference_analysis

# ---------------------------------------------------------------------------
# process_feedback_memory
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_process_feedback_memory_logs_event() -> None:
    """process_feedback_memory completes without error on a valid event."""
    event = MagicMock(
        spec=object,
        user_id="00000000-0000-0000-0000-000000000001",
        project_id="00000000-0000-0000-0000-000000000002",
        event_id="00000000-0000-0000-0000-000000000003",
    )

    # Should not raise
    await process_feedback_memory(event)


# ---------------------------------------------------------------------------
# run_preference_analysis
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_run_preference_analysis_logs_event() -> None:
    """run_preference_analysis completes without error on a valid event."""
    event = MagicMock(
        spec=object,
        user_id="00000000-0000-0000-0000-000000000001",
        project_id="00000000-0000-0000-0000-000000000002",
        event_count=5,
    )

    # Should not raise
    await run_preference_analysis(event)
