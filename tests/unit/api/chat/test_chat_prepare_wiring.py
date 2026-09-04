"""Task 6d-1 wiring tests — chat resolves via ModelRegistry.prepare().

Pins the Task-6a/6b/6c structural contract for the bare ``get_model``
chat call site — the model is resolved via the SINGLE assembly point
(``ModelRegistry.prepare``, Task 4) and ``prepared.model`` reaches
``ChatAgent`` while ``prepared.model_settings`` becomes the BASE of the
stream kwargs (the ADR-045 resolver's per-turn ``max_tokens`` cap is
layered on top via ``resolve_chat_run_limits``):

- ``ChatService._stream_agent_response`` (CHAT)

Root cause pinned here (structural audit, "Pipeline 3 — nothing at
all"): the site resolved the model via bare ``get_model``, so the
intent-aware thinking policy and cache settings never applied to the
chat path — only the resolver's output-budget ``max_tokens`` (when a
run-limit resolver is wired at all). The capability intent is a static
property of the site — the same intent the composer call sites
(``composer.build(LLMIntent.CHAT, ...)``) resolve for the feature.

Out of scope (verified, already compliant): the ``usage_limits``
enforcement itself stays owned by the ADR-045 run-limit resolver
(ADR-045 Decision 4) — ``prepare`` receives no limits on this path, so
``prepared.usage_limits`` is ``None`` and the resolver's limits flow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from pydantic_ai.usage import UsageLimits

from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.run_limits import ResolvedRunLimits
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from pydantic_ai.settings import ModelSettings

    from narrare.chat.chat_service import ChatService
    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare_core.chat.contracts import ChatRequest
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.prompts import PromptComposer

_USER_KEY = "sk-user-key"
_USER_BASE_URL = "https://user.example/v1"

_PREPARED_SETTINGS: ModelSettings = {"max_tokens": 12_345}
_RESOLVER_TOKENS = 100

assert _PREPARED_SETTINGS["max_tokens"] != _RESOLVER_TOKENS


def _user_config() -> ResolvedModelConfig:
    """The config a wired-up user's resolver would return (wizard provider)."""
    return ResolvedModelConfig(
        provider_name="zai",
        model_id="glm-4.7",
        temperature=0.7,
        max_tokens=4096,
    )


class _RecordingPrepareRegistry:
    """Fake ModelRegistry mirroring the Task-6b/6c recording fake.

    ``prepare`` mirrors the real single assembly point (Task 4): exactly
    one ``get_model`` resolution, a canned sentinel ``model_settings``
    (so pass-through to the stream is assertable), and the
    ``usage_limits`` pass-through. Calls are recorded in
    ``prepare_calls`` for wiring assertions.
    """

    def __init__(self) -> None:
        self.get_model: AsyncMock = AsyncMock(return_value=MagicMock(spec=object))
        self.prepare_calls: list[dict[str, object]] = []

    async def prepare(
        self,
        config: ResolvedModelConfig,
        *,
        intent: LLMIntent | None = None,
        usage_limits: UsageLimits | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> PreparedModelCall:
        model = await self.get_model(config, api_key=api_key, base_url=base_url)
        prepared = PreparedModelCall(
            model=model,
            model_settings=_PREPARED_SETTINGS,
            usage_limits=usage_limits,
        )
        self.prepare_calls.append(
            {
                "config": config,
                "intent": intent,
                "usage_limits": usage_limits,
                "api_key": api_key,
                "base_url": base_url,
                "prepared": prepared,
            }
        )
        return prepared


class _StubRunLimitResolver:
    """Stub ADR-045 resolver returning a canned per-turn output budget."""

    def __init__(self) -> None:
        self.usage_limits = UsageLimits(output_tokens_limit=_RESOLVER_TOKENS)
        self.resolve_calls: list[dict[str, object]] = []

    def resolve(
        self,
        *,
        config: ResolvedModelConfig,
        budget: object | None,
        invocation_id: UUID,
    ) -> ResolvedRunLimits:
        _ = config, budget
        self.resolve_calls.append({"invocation_id": invocation_id})
        return ResolvedRunLimits(
            invocation_id=invocation_id,
            usage_limits=self.usage_limits,
            model_settings={"max_tokens": _RESOLVER_TOKENS},
            source="stub",
        )


def _make_service(
    registry: _RecordingPrepareRegistry,
    resolver: _StubRunLimitResolver | None,
) -> ChatService:
    """Build a ChatService with the recording registry (+optional resolver)."""
    from narrare.chat.chat_service import ChatService
    from narrare_core.chat.conversation_store import InMemoryConversationStore
    from narrare_core.prompts import PromptComposer

    composer = AsyncMock(spec=PromptComposer)
    composer.build = AsyncMock(
        return_value=ComposedPrompt(system="Chat system.", user="Chat user.")
    )
    return ChatService(
        prompt_composer=cast("PromptComposer", composer),
        model_registry=cast("ModelRegistry", registry),
        conversation_store=cast("SQLAlchemyConversationStore", InMemoryConversationStore()),
        config=_user_config(),
        run_limit_resolver=cast("DefaultRunLimitResolver | None", resolver),
        api_key=_USER_KEY,
        base_url=_USER_BASE_URL,
    )


def _make_request() -> ChatRequest:
    from narrare_core.chat.contracts import ChatRequest

    return ChatRequest(project_id=uuid4(), message="Hello!", conversation_id=None)


class _ChatAgentStub:
    """Minimal ChatAgent stand-in for the RULE-TEST-01 spec requirement."""


async def _drive_ask(
    service: ChatService,
    request: ChatRequest,
) -> dict[str, object]:
    """Drive ``ask`` with ChatAgent + stream bridge patched; capture kwargs."""
    captured: dict[str, object] = {}

    async def _stream_bridge(**kwargs: object) -> AsyncIterator[dict[str, object]]:
        captured.update(kwargs)
        yield {"type": "done", "usage": {}}

    mock_agent = MagicMock(name="mock_agent", spec=_ChatAgentStub)

    with (
        patch(
            "narrare_core.chat.chat_agent.ChatAgent",
            return_value=mock_agent,
        ),
        patch(
            "narrare.chat._sse_stream.stream_agent_events",
            side_effect=_stream_bridge,
        ),
    ):
        gen = await service.ask(request, uuid4())
        async for _ in gen:
            pass
    return captured


class TestChatPrepareWiring:
    """ChatAgent resolves via prepare(CHAT); settings merge into the stream."""

    async def test_ask_resolves_via_prepare_and_layers_resolver_cap(self) -> None:
        """prepare(CHAT) runs once; prepared settings base + resolver cap.

        The ADR-045 resolver owns ``usage_limits``; its per-turn
        ``max_tokens`` cap must override the config-derived value from the
        assembly point, while the assembly point's thinking/cache keys are
        preserved underneath.
        """
        registry = _RecordingPrepareRegistry()
        resolver = _StubRunLimitResolver()
        service = _make_service(registry, resolver)

        captured = await _drive_ask(service, _make_request())

        # Single assembly point with the site intent + user credentials.
        assert len(registry.prepare_calls) == 1
        call = registry.prepare_calls[0]
        assert call["intent"] is LLMIntent.CHAT
        assert call["api_key"] == _USER_KEY
        assert call["base_url"] == _USER_BASE_URL
        assert call["usage_limits"] is None
        # One prepare() → exactly one model resolution (no duplicate).
        registry.get_model.assert_awaited_once()

        # The resolver stayed the usage-limit owner (ADR-045 Decision 4).
        stream_kwargs = cast("dict[str, object]", captured["stream_kwargs"])
        assert stream_kwargs.get("usage_limits") is resolver.usage_limits

        # Prepared settings form the BASE; the resolver cap wins on
        # conflicts (per-turn budget over config-derived cap).
        merged = cast("dict[str, object]", stream_kwargs["model_settings"])
        assert merged["max_tokens"] == _RESOLVER_TOKENS

    async def test_ask_without_resolver_still_applies_prepared_settings(self) -> None:
        """No resolver wired → prepared.model_settings still reach the run.

        Root cause of this migration: without a resolver, the old path
        sent NO settings at all. The single assembly point must close
        that gap.
        """
        registry = _RecordingPrepareRegistry()
        service = _make_service(registry, None)

        captured = await _drive_ask(service, _make_request())

        stream_kwargs = cast("dict[str, object]", captured["stream_kwargs"])
        assert "usage_limits" not in stream_kwargs
        assert stream_kwargs["model_settings"] == _PREPARED_SETTINGS
