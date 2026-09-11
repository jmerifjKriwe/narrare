"""Fakes for PROMPT-003 live-test service unit tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from narrare.prompts.live_test_service import PromptLiveTestApiService
from narrare_core.agents.base import StreamEvent
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.prompts.preview_types import PromptPreview
from narrare_core.shared.errors import ConfigurationError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from pydantic_ai.models import Model
    from pydantic_ai.usage import UsageLimits

    from narrare_core.agents.prompt_live_test_agent import PromptLiveTestAgent
    from narrare_core.prompts.contracts import ContextSnapshot


@dataclass
class FakeResolver:
    """Fake ``ModelRoutingResolver`` — returns a canned ``ResolvedModel``.

    Set ``should_fail=True`` to simulate "no provider configured"
    (the production resolver raises ``ConfigurationError``).
    """

    should_fail: bool = False
    model_id: str = "test-model"
    api_key: str | None = None
    base_url: str | None = None
    calls: list[tuple[LLMIntent, UUID, UUID | None]] = field(default_factory=list)

    async def resolve(
        self,
        intent: LLMIntent,
        user_id: UUID,
        project_id: UUID | None,
    ) -> ResolvedModel:
        self.calls.append((intent, user_id, project_id))
        if self.should_fail:
            raise ConfigurationError(
                "No AI provider configured.",
                code="NO_AI_PROVIDER",
            )
        return ResolvedModel(
            config=ResolvedModelConfig(
                provider_name="test",
                model_id=self.model_id,
            ),
            api_key=self.api_key,
            base_url=self.base_url,
            source="user_default",
        )


@dataclass
class FakeRegistry:
    """Fake ``ModelRegistry`` — returns a sentinel as the pydantic-ai Model.

    ``prepare`` bridges to the same recording ``get_model`` (Task-6a
    pattern) and wraps the sentinel in a ``PreparedModelCall`` with a
    canned sentinel ``model_settings``.
    """

    calls: list[ResolvedModelConfig] = field(default_factory=list)
    prepare_calls: list[ResolvedModelConfig] = field(default_factory=list)

    async def get_model(
        self,
        config: ResolvedModelConfig,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> Model:
        self.calls.append(config)
        # Sentinel — the service passes this to agent_factory; fakes don't inspect it.
        return cast("Model", object())

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
        self.prepare_calls.append(config)
        return PreparedModelCall(
            model=model,
            model_settings={"max_tokens": 12_345},
            usage_limits=usage_limits,
        )


@dataclass
class FakePreview:
    """Fake Core ``PromptPreviewProtocol`` — returns a canned preview."""

    system_prompt: str = "composed system prompt"
    calls: list[tuple[str, ContextSnapshot, str | None]] = field(default_factory=list)

    async def preview(
        self,
        *,
        prompt_id: str,
        snapshot: ContextSnapshot,
        edited_override: str | None = None,
    ) -> PromptPreview:
        self.calls.append((prompt_id, snapshot, edited_override))
        return PromptPreview(
            system_prompt=edited_override or self.system_prompt,
            user_prompt="",
            first_message=None,
            cascade_source="bundled",
            variables=[],
            diagnostics=[],
        )


class FakeAgent:
    """Fake ``PromptLiveTestAgent`` — yields canned ``StreamEvent`` objects."""

    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks

    async def run_stream(
        self,
        prompt: str,
        deps: object,
        **kwargs: object,
    ) -> AsyncIterator[StreamEvent]:
        for chunk in self._chunks:
            yield StreamEvent(type="token", text=chunk)
        yield StreamEvent(type="done", text="".join(self._chunks))


class FailingAgent:
    """Fake agent that raises mid-stream to test SSE error handling (M2)."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def run_stream(
        self,
        prompt: str,
        deps: object,
        **kwargs: object,
    ) -> AsyncIterator[StreamEvent]:
        yield StreamEvent(type="token", text="partial ")
        raise self._error


def make_live_test_service(
    *,
    chunks: list[str] | None = None,
    resolver_should_fail: bool = False,
    agent: FakeAgent | FailingAgent | None = None,
) -> PromptLiveTestApiService:
    """Build a service with all-fake dependencies for unit testing."""
    target_agent: FakeAgent | FailingAgent = (
        agent
        if agent is not None
        else FakeAgent(
            chunks=chunks or ["hello"],
        )
    )

    def factory(*, model: Model) -> PromptLiveTestAgent:
        return cast("PromptLiveTestAgent", target_agent)

    return PromptLiveTestApiService(
        resolver=FakeResolver(should_fail=resolver_should_fail),
        registry=FakeRegistry(),
        preview=FakePreview(),
        agent_factory=factory,
        intent=LLMIntent.WRITE,
    )
