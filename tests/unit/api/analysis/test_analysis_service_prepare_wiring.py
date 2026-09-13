"""Task 6a-2 wiring tests — ANALYSE services resolve via ModelRegistry.prepare().

Companion of ``test_voice_runner_prepare_wiring.py`` (Task 6a): pins the
same structural contract for the three ANALYSE-intent analysis services
(coreference, readability, POV) — each resolves the model via the SINGLE
assembly point (``ModelRegistry.prepare``, Task 4) and forwards the
coherent ``(model, model_settings, usage_limits)`` triple to
``agent.run``.

Root cause pinned here (structural audit, "Pipeline 3 — nothing at
all"): the services resolved the model via bare ``get_model`` and called
``agent.run()`` with NO model_settings and NO usage_limits, so the
intent-aware thinking policy and the ADR-045 output cap never applied to
these analysis paths. The capability intent (``LLMIntent.ANALYSE``) is a
static property of each service — the same value the user-routing
factories (Task 2a) resolve for these capabilities.

Note: readability degrades gracefully (RULE-11) when the AI phase fails,
so its wiring test also asserts the agent actually ran — otherwise a
silent degradation could mask a broken prepare() wiring.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from narrare_core.agents.pov_types import POVDetectedScene, POVDetectionOutput
from narrare_core.agents.readability_types import ReadabilityAgentOutput
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt
from tests.fakes import FakeChapterRepository, FakeNovelRepository
from tests.unit.api._test_helpers import make_chapter, make_novel, seed_repos
from tests.unit.api.analysis._coreference_test_helpers import consume
from tests.unit.api.analysis._coreference_test_helpers import (
    make_agent_output as make_coreference_output,
)
from tests.unit.api.analysis._fakes import FakeComposer

if TYPE_CHECKING:
    from pydantic_ai.usage import UsageLimits

    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

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
    """Fake ModelRegistry mirroring the Task-6a recording fakes.

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


def _assert_prepare_wiring(
    registry: _RecordingPrepareRegistry,
    config: ResolvedModelConfig,
    *,
    mock_agent_cls: MagicMock,
    intent: LLMIntent,
) -> None:
    """Assert the full Task-6a wiring contract for one agent invocation."""
    assert len(registry.prepare_calls) == 1
    call = registry.prepare_calls[0]
    assert call["config"] is config
    assert call["intent"] is intent
    assert call["api_key"] == _USER_KEY
    assert call["base_url"] == _USER_BASE_URL
    # One prepare() → exactly one model resolution (no duplicate).
    assert registry.get_model.await_count == 1

    # The coherent triple reaches the agent boundary, and the agent ran.
    prepared = call["prepared"]
    assert isinstance(prepared, PreparedModelCall)
    assert mock_agent_cls.call_args.kwargs["model"] is prepared.model
    run_kwargs = mock_agent_cls.return_value.run.call_args.kwargs
    assert run_kwargs["model_settings"] is prepared.model_settings
    assert run_kwargs["usage_limits"] is prepared.usage_limits
    assert mock_agent_cls.return_value.run.await_count == 1


class TestAnalyseServicePrepareWiring:
    """The ANALYSE services assemble via prepare() and forward the triple."""

    async def test_coreference_service_prepares_and_forwards_triple(self) -> None:
        from narrare._app.dependencies_services import StaticModelResolution
        from narrare.analysis.coreference_service import CoreferenceService
        from narrare_core.llm import ResolvedModel

        config = _user_config()
        registry = _RecordingPrepareRegistry()
        chapter_repo = MagicMock(spec=["get"], name="ChapterRepository")
        chapter_repo.get = AsyncMock(
            return_value=SimpleNamespace(
                novel_id=uuid4(), content="Alice looked at Bob. She smiled.", title="Ch 1"
            )
        )
        novel_repo = MagicMock(spec=["get_by_id"], name="NovelRepository")
        novel_repo.get_by_id = AsyncMock(
            return_value=SimpleNamespace(writing_language="en", title="Test", genre=None)
        )
        composer = MagicMock(spec=["build"], name="PromptComposer")
        composer.build = AsyncMock(
            return_value=ComposedPrompt(system="system prompt", user="user prompt")
        )
        service = CoreferenceService(
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            model_registry=cast("ModelRegistry", registry),
            # ADR-086: first-use resolution pinned via StaticModelResolution.
            model_resolution=StaticModelResolution(
                ResolvedModel(config=config, api_key=_USER_KEY, base_url=_USER_BASE_URL)
            ),
            composer=cast("PromptComposer", composer),
            kb_context_provider=None,
            invocation_pipeline=None,
        )

        with patch("narrare_core.agents.coreference_agent.CoreferenceAgent") as MockAgent:
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_coreference_output())
            MockAgent.return_value = mock_agent

            events = await consume(service.analyze(chapter_id=uuid4(), user_id=uuid4()))

        _assert_prepare_wiring(registry, config, mock_agent_cls=MockAgent, intent=LLMIntent.ANALYSE)
        assert events[-1].is_final is True

    async def test_readability_service_prepares_and_forwards_triple(self) -> None:
        from narrare._app.dependencies_services import StaticModelResolution
        from narrare.analysis.services.readability_service import ReadabilityService
        from narrare_core.llm import ResolvedModel

        config = _user_config()
        registry = _RecordingPrepareRegistry()
        novel = make_novel()
        ch = make_chapter(
            novel_id=novel.id, content="The cat sat on the mat. The dog ran to the park."
        )
        nr, cr = FakeNovelRepository(), FakeChapterRepository()
        seed_repos(novel, ch, novel_repo=nr, chapter_repo=cr)
        service = ReadabilityService(
            chapter_repo=cr,
            novel_repo=nr,
            model_registry=cast("ModelRegistry", registry),
            # ADR-086: first-use resolution pinned via StaticModelResolution.
            model_resolution=StaticModelResolution(
                ResolvedModel(config=config, api_key=_USER_KEY, base_url=_USER_BASE_URL)
            ),
            composer=FakeComposer(),
        )

        with patch("narrare_core.agents.readability_agent.ReadabilityAgent") as MockAgent:
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=ReadabilityAgentOutput(overall_assessment="ok"))
            MockAgent.return_value = mock_agent

            results = await service.analyze(
                novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id
            )

        _assert_prepare_wiring(registry, config, mock_agent_cls=MockAgent, intent=LLMIntent.ANALYSE)
        assert len(results) == 1

    async def test_pov_service_prepares_and_forwards_triple(self) -> None:
        from narrare._app.dependencies_services import StaticModelResolution
        from narrare.analysis.services.pov_service import POVService
        from narrare_core.llm import ResolvedModel

        config = _user_config()
        registry = _RecordingPrepareRegistry()
        novel = make_novel()
        ch = make_chapter(novel_id=novel.id, content="Alice saw the light.")
        nr, cr = FakeNovelRepository(), FakeChapterRepository()
        seed_repos(novel, ch, novel_repo=nr, chapter_repo=cr)
        service = POVService(
            chapter_repo=cr,
            novel_repo=nr,
            model_registry=cast("ModelRegistry", registry),
            # ADR-086: first-use resolution pinned via StaticModelResolution.
            model_resolution=StaticModelResolution(
                ResolvedModel(config=config, api_key=_USER_KEY, base_url=_USER_BASE_URL)
            ),
            composer=FakeComposer(),
        )
        sentinel_output = POVDetectionOutput(
            scenes=[
                POVDetectedScene(scene_index=0, pov_character="Alice", confidence=0.9),
            ],
            issues=[],
            pov_distribution={"Alice": 1.0},
            switch_count=0,
            analysis_type="third_limited",
        )

        with patch("narrare_core.agents.pov_agent.POVDetectionAgent") as MockAgent:
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=sentinel_output)
            MockAgent.return_value = mock_agent

            result = await service.analyze(
                novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id
            )

        _assert_prepare_wiring(registry, config, mock_agent_cls=MockAgent, intent=LLMIntent.ANALYSE)
        assert result.analysis_type == "third_limited"
