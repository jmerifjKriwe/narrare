"""Lazy model-resolution semantics for ChatService (ADR-086 L12).

The factory (``chat/dependencies.py::get_chat_service``) wires a
``LazyModelResolution``; this file pins the SERVICE-side lazy contract:

- no resolution at construction,
- exactly one resolve at first use, idempotent afterwards,
- ``ask()`` — the SSE entry point, awaited by the router BEFORE the
  ``StreamingResponse`` is constructed — is a first-use site, so
  ``ConfigurationError`` surfaces as a pre-header 400 (RULE-11 —
  AI-mandatory SSE endpoint) and never after headers,
- the novel-ownership gate (IDOR hardening, notes ``_validate_link``
  pattern) runs FIRST — the routing cascade is NEVER invoked when it
  fails (gate-before-resolution, L15 ordering),
- the resolved triple (config + per-user credentials) is threaded
  verbatim into ``ModelRegistry.prepare`` — WHAT unchanged, only WHEN.

Mirrors ``tests/unit/api/writing/test_suggest_service_lazy_resolution.py``
(ADR-086 L36 precedent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from tests.unit.api.chat.conftest import FakeNovelLookup

from narrare.chat.chat_service import ChatService
from narrare_core.chat.contracts import ChatRequest
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pydantic_ai.usage import UsageLimits

    from narrare._app.dependencies_services import ModelResolution
    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare.notes.contracts import OwnedLinkLookupProtocol
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts import PromptComposer


class _CountingResolution:
    """Fake ModelResolution — counts resolve() calls, never caches.

    Exposes the service-level lazy seam (ADR-086): the service must call
    ``resolve()`` exactly once (first use), never at construction.
    """

    def __init__(self, model: ResolvedModel) -> None:
        self._model = model
        self.calls = 0

    async def resolve(self) -> ResolvedModel:
        self.calls += 1
        return self._model


class _RaisingResolution:
    """Fake ModelResolution — the cascade finds no configured provider."""

    async def resolve(self) -> ResolvedModel:
        raise ConfigurationError(
            "No AI provider configured.",
            code="NO_AI_PROVIDER",
        )


def _resolved_model() -> ResolvedModel:
    """A fixed model triple, as the routing cascade would return it."""
    return ResolvedModel(
        config=ResolvedModelConfig(
            provider_name="zai", model_id="glm-4.7", temperature=0.7, max_tokens=4096
        ),
        api_key="sk-user-key",
        base_url=None,
    )


class _RecordingPrepareRegistry:
    """Fake ModelRegistry — records ``prepare`` kwargs (assembly point).

    Returns a real ``PreparedModelCall`` carrying a sentinel model so the
    patched stream leaves (``_drive_ask``) consume it without LLM machinery.
    """

    def __init__(self) -> None:
        self.prepare_calls: list[dict[str, object]] = []
        self.get_model: AsyncMock = AsyncMock(return_value=MagicMock(spec=object))

    async def prepare(
        self,
        config: ResolvedModelConfig,
        *,
        intent: object = None,
        usage_limits: UsageLimits | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> object:
        """Mirror the single assembly point; record the call."""
        from narrare_core.llm._prepared_call import PreparedModelCall

        self.prepare_calls.append(
            {
                "config": config,
                "intent": intent,
                "api_key": api_key,
                "base_url": base_url,
            }
        )
        return PreparedModelCall(
            model=await self.get_model(config, api_key=api_key, base_url=base_url),
            model_settings=None,
            usage_limits=usage_limits,
        )
        return PreparedModelCall(model=self._model, model_settings=None, usage_limits=usage_limits)


def _make_service(
    model_resolution: ModelResolution,
    *,
    novel_lookup: OwnedLinkLookupProtocol | None = None,
    registry: ModelRegistry | None = None,
) -> ChatService:
    """Build a ChatService with the lazy seam injected (test-context shape)."""
    from narrare_core.chat.conversation_store import InMemoryConversationStore
    from narrare_core.prompts import PromptComposer

    return ChatService(
        prompt_composer=cast("PromptComposer", AsyncMock(spec=PromptComposer)),
        model_registry=registry or cast("ModelRegistry", _RecordingPrepareRegistry()),
        conversation_store=cast("SQLAlchemyConversationStore", InMemoryConversationStore()),
        model_resolution=model_resolution,
        novel_lookup=novel_lookup,
    )


async def _drive_ask(service: ChatService, request: ChatRequest) -> None:
    """Drive ``ask()`` to completion with the stream leaves patched.

    Mirrors ``test_chat_prepare_wiring._drive_ask``: the real
    ``_agent_stream`` orchestration runs, while ``ChatAgent`` and the SSE
    bridge are patched so no LLM machinery is touched (unit level).
    """
    from typing import Any

    async def _stream_bridge(**kwargs: object) -> AsyncIterator[dict[str, object]]:
        _ = kwargs
        yield {"type": "done", "usage": {}}

    with (
        patch("narrare_core.chat.chat_agent.ChatAgent", return_value=MagicMock(spec=object)),
        patch(
            "narrare.chat._sse_stream.stream_agent_events",
            side_effect=cast("Any", _stream_bridge),
        ),
    ):
        gen = await service.ask(request, uuid4())
        async for _ in gen:
            pass


def _request() -> ChatRequest:
    """A project-less chat request (skips the project tiers cleanly)."""
    return ChatRequest(project_id=None, message="Hello!")


class TestLazyResolutionContract:
    """ADR-086 lazy resolution at the ChatService boundary."""

    async def test_no_resolution_at_construction(self) -> None:
        """Construction must not touch the routing cascade."""
        counting = _CountingResolution(_resolved_model())

        _make_service(counting)

        assert counting.calls == 0

    async def test_ensure_resolved_resolves_once_and_is_idempotent(self) -> None:
        """First use resolves exactly once; repeat calls hit the cache."""
        counting = _CountingResolution(_resolved_model())
        service = _make_service(counting)

        first = await service.ensure_resolved()
        second = await service.ensure_resolved()

        assert counting.calls == 1
        assert first is second

    async def test_ask_resolves_exactly_once(self) -> None:
        """The streaming entry point is a first-use site — one resolve."""
        counting = _CountingResolution(_resolved_model())
        service = _make_service(counting)

        await _drive_ask(service, _request())

        assert counting.calls == 1

    async def test_configuration_error_propagates_from_ask(self) -> None:
        """RULE-11 / ADR-086: the cascade's ``ConfigurationError``
        (unconfigured provider) propagates from the entry point — the
        service never swallows it, and because the router awaits
        ``ask()`` before constructing the ``StreamingResponse``, the 400
        fires BEFORE any SSE headers."""
        service = _make_service(_RaisingResolution())

        with pytest.raises(ConfigurationError):
            await service.ask(_request(), uuid4())


class TestGateBeforeResolution:
    """Ownership gates stay ahead of the routing cascade (MUST-NOT-change)."""

    async def test_novel_ownership_gate_stays_ahead_of_resolution(self) -> None:
        """A foreign project_id is rejected with ``NotFoundError`` and the
        routing cascade is NEVER invoked (L15 ordering)."""
        counting = _CountingResolution(_resolved_model())
        service = _make_service(counting, novel_lookup=FakeNovelLookup())

        with pytest.raises(NotFoundError, match="Novel"):
            await service.ask(ChatRequest(project_id=uuid4(), message="Hello!"), uuid4())

        assert counting.calls == 0


class TestResolvedTripleThreading:
    """The cached triple reaches the model resolution point verbatim."""

    async def test_ask_threads_resolved_triple_into_prepare(self) -> None:
        """Timing-only invariant: the eager factory passed the resolved
        ``config`` + credentials into the service — the lazy service
        threads the SAME triple (same objects) into
        ``ModelRegistry.prepare`` at stream time."""
        resolved = _resolved_model()
        counting = _CountingResolution(resolved)
        registry = _RecordingPrepareRegistry()
        service = _make_service(counting, registry=cast("ModelRegistry", registry))

        await _drive_ask(service, _request())

        assert counting.calls == 1
        assert len(registry.prepare_calls) == 1
        call = registry.prepare_calls[0]
        assert call["config"] is resolved.config
        assert call["api_key"] == "sk-user-key"
        assert call["base_url"] is None
        from narrare_core.llm.intents import LLMIntent

        assert call["intent"] is LLMIntent.CHAT
