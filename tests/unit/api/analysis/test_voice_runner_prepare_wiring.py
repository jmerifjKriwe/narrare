"""Task 6a wiring tests — voice runners resolve via ModelRegistry.prepare().

Companion of ``test_deps_user_routing_credentials.py``: that suite pins
WHERE the per-user credentials land (the resolution point); this module
pins the Task-6a structural contract — the runners use the SINGLE
assembly point (``ModelRegistry.prepare``, Task 4) and forward the
coherent ``(model, model_settings, usage_limits)`` triple to
``agent.run``.

Root cause pinned here (structural audit, "Pipeline 3 — nothing at
all"): the runners resolved the model via bare ``get_model`` and called
``agent.run()`` with NO model_settings and NO usage_limits, so the
intent-aware thinking policy and the ADR-045 output cap never applied to
voice analysis. The capability intent (``LLMIntent.VOICE``) is a static
property of each capability-specific runner — the same value the
user-routing factories (Tasks 2a/2b) resolve for these capabilities.

Task 6a-2 extends the suite to the two remaining voice runners
(``run_voice_checker_agent``, ``run_voice_drift_agent``).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from narrare_core.analysis.author_metrics import AuthorMetrics
from narrare_core.kb.schemas.character import VoiceMetrics
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt
from tests.unit.api.analysis._author_voice_drift_test_helpers import (
    FakeModelRegistry as DriftRegistry,
)
from tests.unit.api.analysis._author_voice_drift_test_helpers import (
    make_drift_result,
)
from tests.unit.api.analysis._author_voice_test_helpers import (
    FakeModelRegistry as AuthorVoiceRegistry,
)
from tests.unit.api.analysis._author_voice_test_helpers import (
    make_agent_output as make_author_voice_output,
)
from tests.unit.api.analysis._character_voice_test_helpers import (
    FakeModelRegistry as CharacterVoiceRegistry,
)
from tests.unit.api.analysis._character_voice_test_helpers import (
    make_agent_output as make_character_voice_output,
)
from tests.unit.api.analysis._voice_check_test_helpers import (
    FakeComposer as VoiceCheckFakeComposer,
)
from tests.unit.api.analysis._voice_check_test_helpers import (
    FakeModelRegistry as VoiceCheckRegistry,
)
from tests.unit.api.analysis._voice_check_test_helpers import (
    make_agent_output as make_voice_check_output,
)
from tests.unit.api.analysis._voice_drift_test_helpers import (
    FakeModelRegistry as VoiceDriftRegistry,
)
from tests.unit.api.analysis._voice_drift_test_helpers import (
    make_drift_result as make_voice_drift_result,
)

if TYPE_CHECKING:
    from narrare_core.llm.gateway import ModelRegistry

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


class TestVoiceRunnerPrepareWiring:
    """The runners assemble via prepare() and forward the coherent triple."""

    async def test_author_voice_runner_prepares_and_forwards_triple(self) -> None:
        from narrare.analysis.author_voice_agent_runner import run_author_voice_agent

        config = _user_config()
        registry = AuthorVoiceRegistry()
        sentinel_output = make_author_voice_output()

        with patch("narrare_core.agents.author_voice_agent.AuthorVoiceAgent") as MockAgent:
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=sentinel_output)
            MockAgent.return_value = mock_agent

            output = await run_author_voice_agent(
                chapter_prose="A quiet chapter of prose.",
                voice_metrics=VoiceMetrics(),
                author_metrics=AuthorMetrics(),
                novel_title="Test Novel",
                novel_genre="fantasy",
                novel_id=uuid4(),
                language="en",
                model_registry=cast("ModelRegistry", registry),
                model_config=config,
                composed_prompt=ComposedPrompt(system="system prompt", user="user prompt"),
                api_key=_USER_KEY,
                base_url=_USER_BASE_URL,
            )

        # Single assembly point — exactly one prepare() call with the
        # capability intent and the forwarded per-user credentials.
        assert len(registry.prepare_calls) == 1
        call = registry.prepare_calls[0]
        assert call["config"] is config
        assert call["intent"] is LLMIntent.VOICE
        assert call["api_key"] == _USER_KEY
        assert call["base_url"] == _USER_BASE_URL
        # One prepare() → exactly one model resolution (no duplicate).
        assert registry.get_model.await_count == 1

        # The coherent triple reaches the agent boundary.
        prepared = call["prepared"]
        assert isinstance(prepared, PreparedModelCall)
        assert MockAgent.call_args.kwargs["model"] is prepared.model
        run_kwargs = mock_agent.run.call_args.kwargs
        assert run_kwargs["model_settings"] is prepared.model_settings
        assert run_kwargs["usage_limits"] is prepared.usage_limits
        assert output is sentinel_output

    async def test_character_voice_runner_prepares_and_forwards_triple(self) -> None:
        from narrare.analysis.character_voice_agent_runner import (
            run_character_voice_agent,
        )

        config = _user_config()
        registry = CharacterVoiceRegistry()
        sentinel_output = make_character_voice_output()

        with patch("narrare_core.agents.character_voice_agent.CharacterVoiceAgent") as MockAgent:
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=sentinel_output)
            MockAgent.return_value = mock_agent

            output = await run_character_voice_agent(
                utterances=[],
                metrics={},
                character_names=[],
                novel_title="Test Novel",
                novel_genre="fantasy",
                novel_id=uuid4(),
                language="en",
                model_registry=cast("ModelRegistry", registry),
                model_config=config,
                composed_prompt=ComposedPrompt(system="system prompt", user="user prompt"),
                api_key=_USER_KEY,
                base_url=_USER_BASE_URL,
            )

        assert len(registry.prepare_calls) == 1
        call = registry.prepare_calls[0]
        assert call["config"] is config
        assert call["intent"] is LLMIntent.VOICE
        assert call["api_key"] == _USER_KEY
        assert call["base_url"] == _USER_BASE_URL
        assert registry.get_model.await_count == 1

        prepared = call["prepared"]
        assert isinstance(prepared, PreparedModelCall)
        assert MockAgent.call_args.kwargs["model"] is prepared.model
        run_kwargs = mock_agent.run.call_args.kwargs
        assert run_kwargs["model_settings"] is prepared.model_settings
        assert run_kwargs["usage_limits"] is prepared.usage_limits
        assert output is sentinel_output

    async def test_author_voice_drift_runner_prepares_and_forwards_triple(self) -> None:
        from narrare.analysis.author_voice_drift_agent_runner import (
            run_author_voice_drift_agent,
        )

        config = _user_config()
        registry = DriftRegistry()
        sentinel_output = make_drift_result()

        with patch(
            "narrare.analysis.author_voice_drift_agent_runner.AuthorVoiceDriftAgent"
        ) as MockAgent:
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=sentinel_output)
            MockAgent.return_value = mock_agent

            output = await run_author_voice_drift_agent(
                composed_prompt=ComposedPrompt(system="system prompt", user="user prompt"),
                descriptive_profile="The narrator favours long sentences.",
                trend=[],
                jumps=[],
                chapter_meta=[],
                novel=SimpleNamespace(title="Test Novel", genre="fantasy"),
                language="en",
                novel_id=uuid4(),
                model_registry=cast("ModelRegistry", registry),
                model_config=config,
                api_key=_USER_KEY,
                base_url=_USER_BASE_URL,
            )

        assert len(registry.prepare_calls) == 1
        call = registry.prepare_calls[0]
        assert call["config"] is config
        assert call["intent"] is LLMIntent.VOICE
        assert call["api_key"] == _USER_KEY
        assert call["base_url"] == _USER_BASE_URL
        assert registry.get_model.await_count == 1

        prepared = call["prepared"]
        assert isinstance(prepared, PreparedModelCall)
        assert MockAgent.call_args.kwargs["model"] is prepared.model
        run_kwargs = mock_agent.run.call_args.kwargs
        assert run_kwargs["model_settings"] is prepared.model_settings
        assert run_kwargs["usage_limits"] is prepared.usage_limits
        assert output is sentinel_output

    async def test_voice_check_runner_prepares_and_forwards_triple(self) -> None:
        """Task 6a-2: the checker runner assembles via prepare() (VOICE)."""
        from narrare.analysis.voice_check_agent_runner import run_voice_checker_agent

        config = _user_config()
        registry = VoiceCheckRegistry()
        sentinel_output = make_voice_check_output()

        with (
            patch(
                "narrare.analysis.voice_check_agent_runner.CharacterVoiceCheckerAgent"
            ) as MockAgent,
            patch(
                "narrare.analysis.voice_check_agent_runner.resolve_voice_check_prompt",
                new=AsyncMock(
                    return_value=ComposedPrompt(system="system prompt", user="user prompt")
                ),
            ),
            patch(
                "narrare.writing._relationship_helpers.fetch_formatted_relationships",
                new=AsyncMock(return_value=SimpleNamespace(text="")),
            ),
        ):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=sentinel_output)
            MockAgent.return_value = mock_agent

            result = await run_voice_checker_agent(
                utterances=[],
                current_metrics={},
                profiles_by_name={},
                checkable=[],
                novel=SimpleNamespace(title="Test Novel", genre="fantasy"),
                chapter=SimpleNamespace(id=uuid4(), title="Chapter 1"),
                language="en",
                novel_id=uuid4(),
                user_id=uuid4(),
                model_registry=cast("ModelRegistry", registry),
                model_config=config,
                composer=VoiceCheckFakeComposer(),
                invocation_pipeline=None,
                relationship_repo=None,
                api_key=_USER_KEY,
                base_url=_USER_BASE_URL,
            )

        # Single assembly point — exactly one prepare() call with the
        # capability intent and the forwarded per-user credentials.
        assert len(registry.prepare_calls) == 1
        call = registry.prepare_calls[0]
        assert call["config"] is config
        assert call["intent"] is LLMIntent.VOICE
        assert call["api_key"] == _USER_KEY
        assert call["base_url"] == _USER_BASE_URL
        # One prepare() → exactly one model resolution (no duplicate).
        assert registry.get_model.await_count == 1

        # The coherent triple reaches the agent boundary.
        prepared = call["prepared"]
        assert isinstance(prepared, PreparedModelCall)
        assert MockAgent.call_args.kwargs["model"] is prepared.model
        run_kwargs = mock_agent.run.call_args.kwargs
        assert run_kwargs["model_settings"] is prepared.model_settings
        assert run_kwargs["usage_limits"] is prepared.usage_limits
        assert set(result) == {"Elena", "Marc"}

    async def test_voice_drift_runner_prepares_and_forwards_triple(self) -> None:
        """Task 6a-2: the drift runner assembles via prepare() (VOICE)."""
        from narrare.analysis.voice_drift_agent_runner import run_voice_drift_agent

        config = _user_config()
        registry = VoiceDriftRegistry()
        sentinel_output = make_voice_drift_result()

        with patch(
            "narrare.analysis.voice_drift_agent_runner.CharacterVoiceDriftAgent"
        ) as MockAgent:
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=sentinel_output)
            MockAgent.return_value = mock_agent

            output = await run_voice_drift_agent(
                composed_prompt=ComposedPrompt(system="system prompt", user="user prompt"),
                character_name="Alice",
                descriptive_profile="speaks softly",
                trend=[],
                jumps=[],
                chapter_meta=[],
                novel=SimpleNamespace(title="Test Novel", genre="fantasy"),
                language="en",
                model_registry=cast("ModelRegistry", registry),
                model_config=config,
                api_key=_USER_KEY,
                base_url=_USER_BASE_URL,
            )

        assert len(registry.prepare_calls) == 1
        call = registry.prepare_calls[0]
        assert call["config"] is config
        assert call["intent"] is LLMIntent.VOICE
        assert call["api_key"] == _USER_KEY
        assert call["base_url"] == _USER_BASE_URL
        assert registry.get_model.await_count == 1

        prepared = call["prepared"]
        assert isinstance(prepared, PreparedModelCall)
        assert MockAgent.call_args.kwargs["model"] is prepared.model
        run_kwargs = mock_agent.run.call_args.kwargs
        assert run_kwargs["model_settings"] is prepared.model_settings
        assert run_kwargs["usage_limits"] is prepared.usage_limits
        assert output is sentinel_output
