"""Unit tests for the TaskIQ broker and task registration (INFRA-007).

Verifies:
- The broker is importable and configured with a Redis result backend.
- All background tasks are registered with the broker under the expected
  ``task_name`` labels, so they can be resolved via ``broker.find_task()``.
- Decorated stub tasks remain directly awaitable in-process (preserves the
  existing ``narrare.tasks`` calling contract used by older tests).

Importing ``narrare.tasks.broker`` triggers ``narrare.tasks.__init__``, which
imports every task module so all tasks register on the shared broker instance.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend  # type: ignore[import-untyped]

# Make registration explicit and guard against future import reordering.
import narrare.embeddings.tasks as _embeddings_tasks
import narrare.wiki.tasks as _wiki_tasks
from narrare.tasks import process_feedback_memory, run_preference_analysis

# Importing the broker registers all tasks (package __init__ imports modules).
from narrare.tasks.broker import broker

# ---------------------------------------------------------------------------
# Broker configuration
# ---------------------------------------------------------------------------


class TestBrokerConfiguration:
    def test_broker_is_redis_list_queue_broker(self) -> None:
        """Broker is a Redis-backed ListQueueBroker."""
        assert isinstance(broker, ListQueueBroker)

    def test_broker_has_redis_result_backend(self) -> None:
        """A RedisAsyncResultBackend is attached for task results."""
        assert isinstance(broker.result_backend, RedisAsyncResultBackend)

    def test_broker_not_worker_process_by_default(self) -> None:
        """Default process is the API server, not the taskiq worker."""
        assert broker.is_worker_process is False


# ---------------------------------------------------------------------------
# Task registration
# ---------------------------------------------------------------------------

WIKI_TASK_NAMES = [
    "wiki_generate_entity",
    "wiki_generate_chapter",
    "wiki_mark_all_stale",
    "wiki_refresh_summary",
]


class TestTaskRegistration:
    def test_task_modules_imported_for_registration(self) -> None:
        """Side-effect imports are present (registration side effect)."""
        assert _embeddings_tasks is not None
        assert _wiki_tasks is not None

    def test_embed_source_task_registered(self) -> None:
        """Embedding generation task is registered."""
        assert broker.find_task("embed_source") is not None

    @pytest.mark.parametrize("name", WIKI_TASK_NAMES)
    def test_wiki_tasks_registered(self, name: str) -> None:
        """All wiki background tasks are registered."""
        assert broker.find_task(name) is not None

    def test_feedback_memory_task_registered(self) -> None:
        """Feedback memory stub is registered for future wiring."""
        assert broker.find_task("process_feedback_memory") is not None

    def test_preference_analysis_task_registered(self) -> None:
        """Preference analysis stub is registered for future wiring."""
        assert broker.find_task("run_preference_analysis") is not None

    def test_unknown_task_returns_none(self) -> None:
        """Unknown task names resolve to None, not raise."""
        assert broker.find_task("does_not_exist") is None

    def test_all_wiki_task_names_in_registry(self) -> None:
        """Every wiki task name resolves via get_all_tasks()."""
        all_names = set(broker.get_all_tasks())
        for name in WIKI_TASK_NAMES:
            assert name in all_names


# ---------------------------------------------------------------------------
# Decorated tasks stay directly callable (in-process execution path)
# ---------------------------------------------------------------------------


class TestDirectCallability:
    @pytest.mark.anyio
    async def test_decorated_feedback_task_runs_in_process(self) -> None:
        """Decorated stub still executes directly when awaited (not enqueued)."""
        event = MagicMock(
            spec=object,
            user_id="00000000-0000-0000-0000-000000000001",
            project_id="00000000-0000-0000-0000-000000000002",
            event_id="00000000-0000-0000-0000-000000000003",
        )
        # Should run the original function, not raise.
        await process_feedback_memory(event)

    @pytest.mark.anyio
    async def test_decorated_preference_task_runs_in_process(self) -> None:
        """Decorated preference stub still executes directly when awaited."""
        event = MagicMock(
            spec=object,
            user_id="00000000-0000-0000-0000-000000000001",
            project_id="00000000-0000-0000-0000-000000000002",
            event_count=5,
        )
        await run_preference_analysis(event)


# ---------------------------------------------------------------------------
# KB embedding hook enqueues via broker (INFRA-007)
# ---------------------------------------------------------------------------


class TestKBHookEnqueuesViaBroker:
    """``EmbeddingHookManager._dispatch_task`` enqueues the embed_source task."""

    @pytest.mark.anyio
    async def test_dispatch_enqueues_embed_source(self) -> None:
        """_dispatch_task enqueues embed_source with serializable kwargs."""
        from unittest.mock import AsyncMock, MagicMock, patch
        from uuid import uuid4

        from narrare.kb.embedding_hooks import EmbeddingHookManager

        source_id = uuid4()
        real_task = broker.find_task("embed_source")
        fake_task = MagicMock(spec=type(real_task))
        fake_task.kiq = AsyncMock()
        fake_broker = MagicMock(spec=type(broker))
        fake_broker.find_task.return_value = fake_task

        manager = EmbeddingHookManager()
        with patch("narrare.kb.embedding_hooks.broker", fake_broker):
            await manager._dispatch_task(source_id, "body text", trigger="create")

        fake_broker.find_task.assert_called_once_with("embed_source")
        fake_task.kiq.assert_awaited_once_with(
            source_type="kb_entry",
            source_id=str(source_id),
            content="body text",
        )

    @pytest.mark.anyio
    async def test_dispatch_warns_when_task_not_registered(self) -> None:
        """A missing embed_source registration is logged, not raised."""
        from unittest.mock import MagicMock, patch
        from uuid import uuid4

        from narrare.kb.embedding_hooks import EmbeddingHookManager

        fake_broker = MagicMock(spec=type(broker))
        fake_broker.find_task.return_value = None

        manager = EmbeddingHookManager()
        with patch("narrare.kb.embedding_hooks.broker", fake_broker):
            # Should not raise.
            await manager._dispatch_task(uuid4(), "content", trigger="update")

        fake_broker.find_task.assert_called_once_with("embed_source")


# ---------------------------------------------------------------------------
# Monitoring endpoint (INFRA-007)
# ---------------------------------------------------------------------------


class TestTaskStatusEndpoint:
    def test_status_returns_registered_tasks(self) -> None:
        """GET /tasks/status returns 200 and the registered task list."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from narrare.tasks.router import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/tasks/status")

        assert response.status_code == 200
        data = response.json()
        assert data["is_worker_process"] is False
        assert data["broker_started"] is True
        assert data["registered_task_count"] == len(broker.get_all_tasks())
        assert "embed_source" in data["registered_tasks"]
        # Every registered task name is reported.
        for name in ("embed_source", "wiki_generate_entity", "process_feedback_memory"):
            assert name in data["registered_tasks"]
