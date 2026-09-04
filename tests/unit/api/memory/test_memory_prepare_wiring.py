"""Task 6d-2 wiring tests — memory domain resolves via ModelRegistry.prepare().

Pins the Task-6a/6b/6c structural contract for the bare ``get_model`` +
``agent.run()`` memory call site — the model is resolved via the SINGLE
assembly point (``ModelRegistry.prepare``, Task 4) and the coherent
``(model, model_settings, usage_limits)`` triple is forwarded to
``agent.run``:

- ``PreferenceAnalysisService._run_agent`` (EXTRACT)

Root cause pinned here (structural audit, "Pipeline 3 — nothing at
all"): the site resolved the model via bare ``get_model`` and called
``agent.run()`` with NO model_settings and NO usage_limits, so the
intent-aware thinking policy and the ADR-045 output cap never applied
to the preference-analysis path. The capability intent is a static
property of the site — the same intent the invocation context
(``feature_id="memory_preference_analysis"``) and the composer fallback
(``composer.build(LLMIntent.EXTRACT, ...)``) already resolve.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.intents import LLMIntent
from tests.fakes import (
    FakeFeedbackRepository,
    FakePreferenceProfileRepository,
    FakePromptComposer,
)

if TYPE_CHECKING:
    from narrare_core.llm.gateway import ModelRegistry

_USER_KEY = "sk-user-key"
_USER_BASE_URL = "https://user.example/v1"


def _user_config() -> ResolvedModelConfig:
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
        usage_limits: Any = None,
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


def _seed_events(feedback_repo: FakeFeedbackRepository, count: int) -> tuple[Any, Any]:
    """Seed the fake repo with minimal event-like objects for analysis."""
    from narrare.memory.models import FeedbackEventModel

    user_id = uuid4()
    project_id = uuid4()
    for _ in range(count):
        event = FeedbackEventModel(
            user_id=user_id,
            project_id=project_id,
            suggestion_id=uuid4(),
            action="accept",
            intent="write",
            suggestion_text="Seeded event.",
        )
        feedback_repo.seed(event)
    return user_id, project_id


class TestPreferenceAnalysisPrepareWiring:
    """PreferenceAnalysisAgent resolves via prepare(EXTRACT) + credentials."""

    async def test_analyze_resolves_via_prepare_with_extract_intent(self) -> None:
        from narrare.memory.analysis_service import PreferenceAnalysisService
        from narrare_core.agents.preference_analysis_types import (
            PreferenceAnalysisOutput,
        )

        config = _user_config()
        registry = _RecordingPrepareRegistry()
        feedback_repo = FakeFeedbackRepository()
        profile_repo = FakePreferenceProfileRepository()
        user_id, project_id = _seed_events(feedback_repo, 10)

        service = PreferenceAnalysisService(
            registry=cast("ModelRegistry", registry),
            feedback_repo=feedback_repo,
            profile_repo=profile_repo,
            composer=FakePromptComposer(),
            config=config,
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )
        output = MagicMock(spec=PreferenceAnalysisOutput)
        output.summary = "Prefers concise prose."
        output.confidence = 0.8
        output.style_patterns = ["concise"]
        output.content_patterns = []
        output.avoidance_patterns = []
        agent = AsyncMock(run=AsyncMock(return_value=output))

        with patch(
            "narrare_core.agents.preference_analysis_agent.PreferenceAnalysisAgent",
            return_value=agent,
        ) as mock_agent_cls:
            await service.analyze(user_id, project_id)

        # Single assembly point with the site intent + user credentials.
        assert len(registry.prepare_calls) == 1
        call = registry.prepare_calls[0]
        assert call["config"] is config
        assert call["intent"] is LLMIntent.EXTRACT
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
        # No run-limit resolver is wired on this path (Task 6d concern,
        # same as 6a/6b/6c): the pass-through value is None.
        assert prepared.usage_limits is None
        assert mock_agent_cls.return_value.run.await_count == 1
