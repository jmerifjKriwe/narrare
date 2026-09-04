"""Task 7 wiring tests — prompt live-test resolves via ModelRegistry.prepare().

Pins the Task-6a-6d structural contract for the last bare ``get_model``
call site in the prompts domain — the model is resolved via the SINGLE
assembly point (``ModelRegistry.prepare``, Task 4) and the coherent
 ``(model, model_settings, usage_limits)`` triple is forwarded to the
agent streaming boundary:

- ``PromptLiveTestApiService.stream_live_test`` (WRITE intent) —
  ``prepared.model`` reaches the agent factory and the settings half of
  the triple reaches ``agent.run_stream``.

Root cause pinned here (structural audit): the site resolved via bare
``get_model`` and streamed with NO model_settings and NO usage_limits,
so the intent-aware thinking policy never applied to the live-test
path. The capability intent is the service's routing intent
(``LLMIntent.WRITE`` default — the same value the resolver is invoked
with), and the credentials come from the resolved ``ResolvedModel``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from narrare.prompts.live_test_service import PromptLiveTestApiService
from narrare.prompts.schemas_prompt_ux import LiveTestRequest
from narrare_core.agents.base import StreamEvent
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.intents import LLMIntent
from tests.unit.api.prompts.live_test_service_fakes import FakePreview, FakeResolver

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from pydantic_ai.models import Model
    from pydantic_ai.usage import UsageLimits

    from narrare_core.agents.prompt_live_test_agent import PromptLiveTestAgent
    from narrare_core.llm.model_config import ResolvedModelConfig

_USER_KEY = "sk-user-key"
_USER_BASE_URL = "https://user.example/v1"
_PROMPT_ID = "writing/en/new_chapter"


class _RecordingPrepareRegistry:
    """Fake ModelRegistry mirroring the Task-6b/6c recording fakes.

    ``prepare`` mirrors the real single assembly point (Task 4): exactly
    one ``get_model`` resolution, a canned sentinel ``model_settings``
    (so pass-through to ``agent.run_stream`` is assertable), and the
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
            model_settings={"max_tokens": 12_345},
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


class _RecordingAgent:
    """Stub ``PromptLiveTestAgent`` recording run_stream kwargs (RULE-TEST-01)."""

    def __init__(self) -> None:
        self.run_stream_kwargs: dict[str, object] = {}

    async def run_stream(
        self,
        prompt: str,
        deps: object,
        **kwargs: object,
    ) -> AsyncIterator[StreamEvent]:
        self.run_stream_kwargs = kwargs
        yield StreamEvent(type="token", text="ok")
        yield StreamEvent(type="done", text="ok")


class _RecordingAgentFactory:
    """Factory stub recording the model each agent is built from."""

    def __init__(self) -> None:
        self.models: list[object] = []
        self.agent = _RecordingAgent()

    def __call__(self, *, model: Model) -> PromptLiveTestAgent:
        self.models.append(model)
        return cast("PromptLiveTestAgent", self.agent)


def _make_wired_service(
    resolver: FakeResolver,
    registry: _RecordingPrepareRegistry,
    factory: _RecordingAgentFactory,
) -> PromptLiveTestApiService:
    return PromptLiveTestApiService(
        resolver=resolver,
        registry=registry,
        preview=FakePreview(),
        agent_factory=factory,
        intent=LLMIntent.WRITE,
    )


async def test_stream_live_test_resolves_via_prepare_and_forwards_triple() -> None:
    resolver = FakeResolver(api_key=_USER_KEY, base_url=_USER_BASE_URL)
    registry = _RecordingPrepareRegistry()
    factory = _RecordingAgentFactory()
    service = _make_wired_service(resolver, registry, factory)

    user_id: UUID = uuid4()
    request = LiveTestRequest(variables={"language": "en"}, acknowledge_token_cost=True)
    metadata = await service.validate_live_test(
        prompt_id=_PROMPT_ID,
        request=request,
        user_id=str(user_id),
    )

    frames: list[str] = [
        frame
        async for frame in service.stream_live_test(
            prompt_id=_PROMPT_ID,
            request=request,
            user_id=str(user_id),
            metadata=metadata,
        )
    ]

    # The stream actually ran to completion.
    assert any("event: done" in frame for frame in frames)
    # Single assembly point with the site intent + resolved credentials.
    assert len(registry.prepare_calls) == 1
    call = registry.prepare_calls[0]
    # Config comes from the resolver's ResolvedModel (canned test model).
    assert cast("ResolvedModelConfig", call["config"]).model_id == resolver.model_id
    assert call["intent"] is LLMIntent.WRITE
    assert call["api_key"] == _USER_KEY
    assert call["base_url"] == _USER_BASE_URL
    # One prepare() → exactly one model resolution (no duplicate).
    registry.get_model.assert_awaited_once()
    prepared = cast("PreparedModelCall", call["prepared"])
    # The agent is built from prepared.model.
    assert factory.models == [prepared.model]
    # The settings half of the triple reaches the agent run boundary.
    assert factory.agent.run_stream_kwargs["model_settings"] is prepared.model_settings
    assert factory.agent.run_stream_kwargs["usage_limits"] is prepared.usage_limits
    # No run-limit resolver is wired on this path (Task 7 concern, same
    # as 6a/6b/6c/6d): the pass-through value is None.
    assert prepared.usage_limits is None
