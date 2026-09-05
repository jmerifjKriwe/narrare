"""Shared fakes for the Task-6c KB prepare() wiring tests (RULE-04 split).

Mirrors the ``_assist_fakes.py`` / ``_merge_test_helpers.py`` pattern:
single home for the recording registry, composer fakes, and the wiring
assertion helper so ``test_kb_prepare_wiring.py`` (improve + merge) and
``test_kb_worldbuilding_prepare_wiring.py`` (worldbuilding) stay under
the RULE-04 test-file hard limit without duplicating fakes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from pydantic_ai.usage import UsageLimits

    from narrare_core.llm.intents import LLMIntent

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


class _FakeComposer:
    """Fake PromptComposer returning simple prompts."""

    def __init__(self) -> None:
        self.build: AsyncMock = AsyncMock(
            return_value=ComposedPrompt(system="System prompt.", user="User prompt.")
        )


class _ComposedInvocation:
    """Stand-in for ``ComposedInvocation`` (Mode 1)."""

    def __init__(self) -> None:
        self.composed_prompt: ComposedPrompt = ComposedPrompt(
            system="System prompt.", user="User prompt."
        )


class _AssertWiring:
    """Shared assertion helper for one prepare→agent invocation."""

    def __init__(
        self,
        registry: _RecordingPrepareRegistry,
        config: ResolvedModelConfig,
    ) -> None:
        self.registry = registry
        self.config = config

    def call(self, index: int = 0) -> dict[str, object]:
        assert len(self.registry.prepare_calls) > index
        return self.registry.prepare_calls[index]

    def agent_assembly(
        self,
        mock_agent_cls: MagicMock,
        call: dict[str, object],
        *,
        run_arg: str = "model",
    ) -> None:
        """Assert the coherent triple reaches the agent boundary."""
        prepared = call["prepared"]
        assert isinstance(prepared, PreparedModelCall)
        assert mock_agent_cls.call_args.kwargs[run_arg] is prepared.model
        run_kwargs = mock_agent_cls.return_value.run.call_args.kwargs
        assert run_kwargs["model_settings"] is prepared.model_settings
        assert run_kwargs["usage_limits"] is prepared.usage_limits
        # Task 3 follow-up: the ADR-045 run-limit resolver is wired on
        # these KB paths — the pass-through value is a resolved, non-None
        # UsageLimits (capped to the config's max_tokens).
        assert prepared.usage_limits is not None
