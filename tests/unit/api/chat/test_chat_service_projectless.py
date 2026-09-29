"""Unit tests for project-less chat flow (NOTES-001 §6b).

Without project_id the service must still create a conversation, compose a
prompt, and stream a response — KB/project enrichment is skipped. Uses the
shared fixtures from tests/unit/api/chat/conftest.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from structlog.testing import capture_logs
from tests.unit.api.chat.conftest import _async_gen

from narrare_core.chat.contracts import ChatRequest

if TYPE_CHECKING:
    from unittest.mock import AsyncMock

    from narrare.chat.chat_service import ChatService
    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare_core.ai_invocation.models import PromptInvocationContext
    from narrare_core.chat.conversation_store import InMemoryConversationStore


def _mock_chat_agent() -> MagicMock:
    """Build a ChatAgent mock streaming one token + done (conftest pattern).

    The brief's tests need ``ChatAgent`` patched: the real agent rejects the
    mock registry model (``UserError: Unknown model``). Same pattern as
    test_chat_service.py / test_chat_service_invocation_pipeline.py.
    """
    from narrare_core.agents.base import StreamEvent
    from narrare_core.chat.chat_agent import ChatAgent

    mock_agent = MagicMock(name="mock_agent", spec=ChatAgent)
    mock_agent.run_stream = lambda *a, **kw: _async_gen(
        StreamEvent(type="token", text="Answer"),
        StreamEvent(type="done", text="Answer", usage={}, new_messages=[]),
    )
    return mock_agent


class TestProjectlessAsk:
    async def test_ask_without_project_creates_conversation_and_streams(
        self,
        service: object,
        in_memory_store: object,
    ) -> None:
        user_id = uuid4()
        request = ChatRequest(message="Craft question without a project")

        events = []
        with patch(
            "narrare_core.chat.chat_agent.ChatAgent",
            return_value=_mock_chat_agent(),
        ):
            stream = await cast("ChatService", service).ask(request, user_id)
            async for event in stream:
                events.append(event)

        assert events[0]["type"] == "meta"
        conv_id = UUID(str(events[0]["conversation_id"]))
        assert events[-1]["type"] == "done"

        # The conversation persists with a NULL project.
        stored_project = await cast(
            "InMemoryConversationStore", (in_memory_store)
        ).get_conversation_project_id(conv_id, user_id)
        assert stored_project is None

    async def test_ask_with_project_still_enriches(
        self,
        service: object,
        in_memory_store: object,
    ) -> None:
        """Regression: legacy project-scoped flow unchanged."""
        user_id = uuid4()
        project_id = uuid4()
        request = ChatRequest(project_id=project_id, message="Hello")

        events = []
        with patch(
            "narrare_core.chat.chat_agent.ChatAgent",
            return_value=_mock_chat_agent(),
        ):
            stream = await cast("ChatService", service).ask(request, user_id)
            async for event in stream:
                events.append(event)

        conv_id = UUID(str(events[0]["conversation_id"]))
        stored_project = await cast(
            "InMemoryConversationStore", (in_memory_store)
        ).get_conversation_project_id(conv_id, user_id)
        assert stored_project == project_id


class TestProjectlessSkipLog:
    """The §6b skip is logged with identifying context (RULE-11 + log fields)."""

    async def test_projectless_skip_log_carries_user_id(
        self,
        service: object,
    ) -> None:
        """``chat_project_context_skipped`` names the user, not just the chat.

        Without ``user_id`` the skip log cannot be correlated to an account
        when debugging enrichment gaps.
        """
        user_id = uuid4()
        request = ChatRequest(message="Craft question without a project")

        with (
            patch(
                "narrare_core.chat.chat_agent.ChatAgent",
                return_value=_mock_chat_agent(),
            ),
            capture_logs() as logs,
        ):
            async for _ in await cast("ChatService", service).ask(request, user_id):
                pass

        skips = [e for e in logs if e.get("event") == "chat_project_context_skipped"]
        assert skips, "expected a chat_project_context_skipped info log"
        assert skips[0].get("user_id") == str(user_id)
        assert skips[0].get("conversation_id")


class _SpyEnricher:
    """ContextEnricher spy — records ``enrich()`` calls, context unchanged.

    Behavioral detector for "did the invocation pipeline run": wiring this
    into a real ``InvocationPipeline`` and counting calls proves whether
    project-correlated enrichment was consulted (ADR-030: real fake, not a
    MagicMock that stays green through refactors).
    """

    def __init__(self) -> None:
        self.calls = 0

    async def enrich(self, context: PromptInvocationContext) -> PromptInvocationContext:
        self.calls += 1
        return context


class TestProjectlessEnrichmentSkip:
    """NOTES-001 §6b: without a project, KB/project enrichment tiers are skipped."""

    @staticmethod
    def _service_with_pipeline(
        mock_composer: AsyncMock,
        mock_registry: AsyncMock,
        in_memory_store: InMemoryConversationStore,
        mock_config: MagicMock,
        spy: _SpyEnricher,
    ) -> ChatService:
        from tests.unit.api.chat.conftest import _static_resolution

        from narrare.chat.chat_service import ChatService
        from narrare_core.ai_invocation.pipeline import InvocationPipeline

        return ChatService(
            prompt_composer=mock_composer,
            model_registry=mock_registry,
            conversation_store=cast("SQLAlchemyConversationStore", in_memory_store),
            model_resolution=_static_resolution(mock_config),
            invocation_pipeline=InvocationPipeline(enrichers=[spy]),
        )

    async def test_projectless_ask_does_not_run_enrichment(
        self,
        mock_composer: AsyncMock,
        mock_registry: AsyncMock,
        in_memory_store: InMemoryConversationStore,
        mock_config: MagicMock,
    ) -> None:
        """Project-less chat passes no pipeline — enrichers never run (§6b)."""
        spy = _SpyEnricher()
        service = self._service_with_pipeline(
            mock_composer, mock_registry, in_memory_store, mock_config, spy
        )

        request = ChatRequest(message="Craft question without a project")
        with patch(
            "narrare_core.chat.chat_agent.ChatAgent",
            return_value=_mock_chat_agent(),
        ):
            async for _ in await service.ask(request, uuid4()):
                pass

        assert spy.calls == 0, "project-less chat must skip enrichment tiers"

    async def test_project_scoped_ask_runs_enrichment(
        self,
        mock_composer: AsyncMock,
        mock_registry: AsyncMock,
        in_memory_store: InMemoryConversationStore,
        mock_config: MagicMock,
    ) -> None:
        """Regression: project-scoped chat still runs the enrichment pipeline."""
        spy = _SpyEnricher()
        service = self._service_with_pipeline(
            mock_composer, mock_registry, in_memory_store, mock_config, spy
        )

        request = ChatRequest(project_id=uuid4(), message="Hello")
        with patch(
            "narrare_core.chat.chat_agent.ChatAgent",
            return_value=_mock_chat_agent(),
        ):
            async for _ in await service.ask(request, uuid4()):
                pass

        assert spy.calls == 1, "project-scoped chat must run enrichment once"
