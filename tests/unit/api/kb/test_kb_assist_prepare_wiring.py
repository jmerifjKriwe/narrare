"""Task 6c-1 wiring tests — KB assist resolves via ModelRegistry.prepare().

Pins the Task-6a/6b structural contract for the KBAssistService agent
assembly: the model is resolved via the SINGLE assembly point
(``ModelRegistry.prepare``, Task 4) and the coherent
``(model, model_settings, usage_limits)`` triple is forwarded to
``agent.run``.

The assist capability intent is not static per feature: the three
public methods (``get_interview_question`` → KB_INTERVIEW,
``get_suggestion`` → KB_SUGGEST, ``get_enhancement`` → KB_ENHANCE)
route through the shared ``_run_agent`` assembly and pass their intent
dynamically. This test pins the canonical default (KB_INTERVIEW —
the assist interview flow) through the shared assembly point; the
other two intents flow through the identical code path with their own
intent value.

Root cause pinned here (structural audit): the site resolved the model
via bare ``get_model`` and called ``agent.run()`` with NO
model_settings and NO usage_limits, so the intent-aware thinking
policy and the ADR-045 output cap never applied to the assist path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch

from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from pydantic_ai.usage import UsageLimits

    from narrare.kb.context_contracts import KBContextProviderProtocol
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts import PromptComposer

_USER_KEY = "sk-user-key"
_USER_BASE_URL = "https://user.example/v1"


def _user_config() -> ResolvedModelConfig:
    """The config a wired-up user's resolver would return (wizard provider)."""
    return ResolvedModelConfig(
        provider_name="zai",
        model_id="glm-4.7",
        temperature=0.7,
        max_tokens=4096,
    )


class _RecordingPrepareRegistry:
    """Fake ModelRegistry mirroring the Task-6b recording fake.

    ``prepare`` mirrors the real single assembly point (Task 4): exactly
    one ``get_model`` resolution, a canned sentinel ``model_settings``
    (so pass-through to ``agent.run`` is assertable), and the
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


class TestAssistPrepareWiring:
    """KBAssistAgent resolves via prepare(<dynamic intent>) with user credentials."""

    async def test_run_agent_resolves_via_prepare_with_dynamic_intent(self) -> None:
        from narrare.kb.assist_service import KBAssistService
        from narrare_core.prompts.composer import ComposedPrompt

        config = _user_config()
        registry = _RecordingPrepareRegistry()

        class _FakeComposer:
            """Fake PromptComposer for DI wiring (build unreachable under Mode 1 patch)."""

            def __init__(self) -> None:
                self.build: AsyncMock = AsyncMock(
                    return_value=ComposedPrompt(system="System prompt.", user="User prompt.")
                )

        provider = MagicMock(spec=["fetch_world_context", "fetch_context", "fetch_entities"])
        provider.fetch_world_context = AsyncMock(return_value="")
        provider.fetch_entities = AsyncMock(return_value=[])
        service = KBAssistService(
            registry=cast("ModelRegistry", registry),
            config=config,
            kb_context_provider=cast("KBContextProviderProtocol", provider),
            prompt_composer=cast("PromptComposer", _FakeComposer()),
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )
        output = MagicMock(spec=["field_key", "question", "reasoning"])
        output.field_key = "backstory"
        output.question = "What shaped her?"
        output.reasoning = "Interview flow."
        agent = AsyncMock(run=AsyncMock(return_value=output))

        composed = ComposedPrompt(system="System prompt.", user="User prompt.")
        invocation = MagicMock(spec=["composed_prompt"])
        invocation.composed_prompt = composed

        with (
            patch(
                "narrare.kb.assist_service.KBAssistAgent",
                return_value=agent,
            ) as MockAgent,
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=invocation),
            ),
        ):
            result = await service._run_agent(
                user_prompt="Test prompt",
                deps=MagicMock(spec=["language", "genre"]),
                intent=LLMIntent.KB_INTERVIEW,
                entity_type="character",
                existing_fields={},
            )

        # prepare() is the single assembly point with the DYNAMIC intent
        # the caller passed (KB_INTERVIEW here) + user credentials.
        assert len(registry.prepare_calls) == 1
        call = registry.prepare_calls[0]
        assert call["config"] is config
        assert call["intent"] is LLMIntent.KB_INTERVIEW
        assert call["api_key"] == _USER_KEY
        assert call["base_url"] == _USER_BASE_URL
        # One prepare() → exactly one model resolution (no duplicate).
        registry.get_model.assert_awaited_once()
        # The coherent triple reaches the agent boundary, and the agent ran.
        prepared = call["prepared"]
        assert isinstance(prepared, PreparedModelCall)
        assert MockAgent.call_args.kwargs["model"] is prepared.model
        run_kwargs = MockAgent.return_value.run.call_args.kwargs
        assert run_kwargs["model_settings"] is prepared.model_settings
        assert run_kwargs["usage_limits"] is prepared.usage_limits
        # Task 3 follow-up: the ADR-045 run-limit resolver is wired —
        # the pass-through value is a resolved, non-None UsageLimits.
        assert prepared.usage_limits is not None
        assert MockAgent.return_value.run.await_count == 1
        assert result.field_key == "backstory"
