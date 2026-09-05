"""Task 6d-1 wiring tests — ai_assist resolves via ModelRegistry.prepare().

Pins the Task-6a/6b/6c structural contract for the bare ``get_model`` +
``agent.run()`` ai_assist call site — the model is resolved via the
SINGLE assembly point (``ModelRegistry.prepare``, Task 4) and the
coherent ``(model, model_settings, usage_limits)`` triple is forwarded
to ``agent.run``:

- ``run_dialogue_coach_agent`` (DIALOGUE_COACH)

Root cause pinned here (structural audit, "Pipeline 3 — nothing at
all"): the site resolved the model via bare ``get_model`` and called
``agent.run()`` with NO model_settings and NO usage_limits, so the
intent-aware thinking policy and the ADR-045 output cap never applied
to the dialogue-coach path. The capability intent is a static property
of the site — the same intent the composer call sites (Mode 1
invocation contexts, ``composer.build``) resolve for the feature
(``dialogue_coach``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch

from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from pydantic_ai.usage import UsageLimits

    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import ComposedPrompt

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
    """Fake ModelRegistry mirroring the Task-6b/6c recording fake.

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


class TestDialogueCoachPrepareWiring:
    """DialogueCoachAgent resolves via prepare(DIALOGUE_COACH) + credentials."""

    async def test_agent_runner_resolves_via_prepare_and_forwards_triple(self) -> None:
        """The runner resolves through prepare() and forwards the triple.

        Pins the Task-4 single assembly point at the dialogue-coach
        resolution site: intent + per-user credentials reach ``prepare``,
        exactly one model resolution happens, and ``prepared.model`` /
        ``prepared.model_settings`` / ``prepared.usage_limits`` all reach
        the agent boundary.
        """
        from uuid import uuid4

        from narrare.ai_assist._agent_runner import run_dialogue_coach_agent
        from narrare_core.agents.dialogue_coach_types import DialogueCoachOutput
        from narrare_core.prompts.composer import ComposedPrompt

        config = _user_config()
        registry = _RecordingPrepareRegistry()
        composed: ComposedPrompt = ComposedPrompt(system="Coach system.", user="Coach user.")
        output = MagicMock(spec=DialogueCoachOutput)
        agent = AsyncMock(run=AsyncMock(return_value=output))

        with (
            patch(
                "narrare_core.agents.dialogue_coach_agent.DialogueCoachAgent",
                return_value=agent,
            ) as mock_agent_cls,
        ):
            result = await run_dialogue_coach_agent(
                selection_text='"Pass me the salt," she said.',
                mode="analyze",
                characters=["Ada"],
                project_title="Test Novel",
                genre="Fantasy",
                language="en",
                voice_profiles_text="Ada speaks warmly.",
                chapter_id=uuid4(),
                model_registry=cast("ModelRegistry", registry),
                model_config=config,
                api_key=_USER_KEY,
                base_url=_USER_BASE_URL,
                composed_prompt=composed,
            )

        assert result is output
        # Single assembly point: one prepare() call with the site intent
        # and the per-user credentials.
        assert len(registry.prepare_calls) == 1
        call = registry.prepare_calls[0]
        assert call["config"] is config
        assert call["intent"] is LLMIntent.DIALOGUE_COACH
        assert call["api_key"] == _USER_KEY
        assert call["base_url"] == _USER_BASE_URL
        # One prepare() → exactly one model resolution (no duplicate).
        registry.get_model.assert_awaited_once()
        # The coherent triple reaches the agent boundary, and the agent ran.
        prepared = cast("PreparedModelCall", call["prepared"])
        assert mock_agent_cls.call_args.kwargs["model"] is prepared.model
        run_kwargs = mock_agent_cls.return_value.run.call_args.kwargs
        assert run_kwargs["model_settings"] is prepared.model_settings
        assert run_kwargs["usage_limits"] is prepared.usage_limits
        # Task 3 follow-up: the ADR-045 run-limit resolver is wired —
        # the pass-through value is a resolved, non-None UsageLimits
        # (capped to the config's max_tokens).
        assert prepared.usage_limits is not None
        assert mock_agent_cls.return_value.run.await_count == 1
