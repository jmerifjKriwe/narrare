"""Unit tests for the AI remap production activation (FO-9 follow-up).

Pins the wiring that lifts the two dormancy gates:
- ``build_remap_items``: lazy agent construction + per-chapter AI/heuristic split
- agent forwarding through ``ai_suggest_stage``
- StoryboardService threading registry/config/credentials into the remap path

Task 6b follow-up: model resolution goes through the single assembly
point ``ModelRegistry.prepare()`` (PLAN — the intent the storyboard
factory routes the config for). The prepared triple now crosses the
core ``AIRemapService.analyze_chapter_role`` boundary IN FULL: the
model half at agent construction, the ``model_settings`` /
``usage_limits`` halves threaded through ``ai_suggest_stage`` into
``analyze_chapter_role`` and on to ``agent.run`` — the 19009e17
kwargs pass-through convention (gap formerly documented in
``_remap_helpers.build_remap_agent``; now closed).

The factory-side injection pins live in ``test_service_factory_wiring.py``.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import pytest

from narrare.planning._remap_helpers import ai_suggest_stage, build_remap_items
from narrare.planning.service import StoryboardService
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.intents import LLMIntent
from narrare_core.planning.remap import AIRemapService
from narrare_core.prompts.composer import ComposedPrompt
from tests.factories import make_chapter
from tests.fakes import FakeChapterRepository, FakeNovelRepository, FakeOutlineRepository
from tests.unit.api.planning.test_storyboard_ai_remap import _seed_chapters, _seed_novel

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.usage import UsageLimits

    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

_SENTINEL_SETTINGS: ModelSettings = {"max_tokens": 12_345}


class TestAISuggestStageAgentForwarding:
    """ai_suggest_stage forwards the agent into the governed remap service."""

    async def test_agent_stage_wins_over_heuristic_when_forwarded(self) -> None:
        """The forwarded agent's stage is returned instead of the heuristic."""
        from narrare_core.planning.adapters import registry as adapter_registry

        adapter = adapter_registry.get("three_act")
        stage = await ai_suggest_stage(
            ai_remap_service=_fake_composer_service(),
            summary="A test summary.",
            structure_type="three_act",
            position=1,
            total=3,
            adapter=adapter,
            agent=_FakeRemapAgent(stage="act-3"),
        )

        assert stage == "act-3"


# ---------------------------------------------------------------------------
# Production activation wiring (FO-9 follow-up)
# ---------------------------------------------------------------------------


def _user_config() -> ResolvedModelConfig:
    """The config a wired-up user's resolver would return."""
    return ResolvedModelConfig(
        provider_name="zai",
        model_id="glm-4.7",
        temperature=0.7,
        max_tokens=4096,
    )


def _adapter(structure_type: str = "five_act") -> object:
    """The real structure adapter for heuristic expectations."""
    from narrare_core.planning.adapters import registry as adapter_registry

    return adapter_registry.get(structure_type)


class _RecordingModelRegistry:
    """Fake ModelRegistry recording prepare calls for wiring pins.

    Mirrors the single assembly point (Task 6b): implements ONLY
    ``prepare`` — no bare ``get_model`` surface — so wiring pins fail
    loudly if a call site bypasses the assembly point.
    """

    def __init__(self, *, error: Exception | None = None) -> None:
        self._error = error
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
        self.prepare_calls.append(
            {
                "config": config,
                "intent": intent,
                "usage_limits": usage_limits,
                "api_key": api_key,
                "base_url": base_url,
                "prepared": None,  # set below (record includes the built triple)
            }
        )
        if self._error is not None:
            raise self._error
        prepared = PreparedModelCall(
            model=cast("Model", object()),
            model_settings=_SENTINEL_SETTINGS,
            usage_limits=usage_limits,
        )
        self.prepare_calls[-1]["prepared"] = prepared
        return prepared


class _FakeRemapComposer:
    """Fake PromptComposer returning a simple governed-shaped prompt."""

    async def build(self, intent: object, context: object) -> ComposedPrompt:
        return ComposedPrompt(system="Stage the chapter.", user="Summary follows.")


class _FakeRemapAgent:
    """Stands in for ChapterSummaryAgent at the analyze_chapter_role seam."""

    def __init__(self, stage: str = "act-2") -> None:
        self._stage = stage
        self.run_calls: list[dict[str, object]] = []

    async def run(
        self,
        *,
        prompt: str,
        deps: object,
        model_settings: object = None,
        usage_limits: object = None,
    ) -> object:
        self.run_calls.append(
            {
                "prompt": prompt,
                "deps": deps,
                "model_settings": model_settings,
                "usage_limits": usage_limits,
            }
        )
        return SimpleNamespace(summary=self._stage)


def _fake_composer_service() -> AIRemapService:
    """AIRemapService with a deterministic composer for wiring tests."""
    composer = cast("PromptComposer", _FakeRemapComposer())
    return AIRemapService(composer=composer)


class TestBuildRemapItems:
    """build_remap_items: lazy agent build + per-chapter AI/heuristic split."""

    async def test_ai_stage_used_when_coverage_and_model_present(self) -> None:
        novel_id = uuid.uuid4()
        chapters = [
            make_chapter(novel_id=novel_id, position=i, summary=f"Summary {i}.") for i in range(3)
        ]
        adapter = _adapter()
        registry = _RecordingModelRegistry()
        config = _user_config()
        agent = _FakeRemapAgent(stage="act-2")

        with (
            patch(
                "narrare_core.agents.summary_agent.ChapterSummaryAgent", return_value=agent
            ) as mock_agent_cls,
        ):
            items = await build_remap_items(
                chapters,
                {},
                adapter,
                "five_act",
                _fake_composer_service(),
                cast("ModelRegistry", registry),
                config,
                api_key="sk-test",
                base_url="https://example.test/v1",
            )

        assert all(item.new_stage == "act-2" for item in items)
        assert len(agent.run_calls) == 3
        assert len(registry.prepare_calls) == 1
        call = registry.prepare_calls[0]
        assert call["config"] is config
        assert call["intent"] is LLMIntent.PLAN
        assert call["usage_limits"] is not None
        assert call["api_key"] == "sk-test"
        assert call["base_url"] == "https://example.test/v1"
        # The FULL prepared triple crosses the AIRemapService boundary:
        # the model half at construction, settings + limits halves at
        # every agent.run (kwargs pass-through, 19009e17 convention).
        prepared = cast("PreparedModelCall", call["prepared"])
        assert mock_agent_cls.call_args.kwargs["model"] is prepared.model
        assert all(run["model_settings"] is prepared.model_settings for run in agent.run_calls)
        assert all(run["usage_limits"] is prepared.usage_limits for run in agent.run_calls)

    async def test_summaryless_chapters_fall_back_to_heuristic(self) -> None:
        novel_id = uuid.uuid4()
        chapters = [
            make_chapter(novel_id=novel_id, position=0, summary="Has summary."),
            make_chapter(novel_id=novel_id, position=1, summary=""),
        ]
        adapter = _adapter()
        agent = _FakeRemapAgent(stage="act-2")

        with patch("narrare_core.agents.summary_agent.ChapterSummaryAgent", return_value=agent):
            items = await build_remap_items(
                chapters,
                {},
                adapter,
                "five_act",
                _fake_composer_service(),
                cast("ModelRegistry", _RecordingModelRegistry()),
                _user_config(),
            )

        five_act_stages = {"exposition", "rising-action", "climax", "falling-action", "resolution"}
        assert items[0].new_stage == "act-2"
        assert items[1].new_stage in five_act_stages
        # Only the summary chapter reached the agent.
        assert len(agent.run_calls) == 1

    async def test_heuristic_when_no_model_config(self) -> None:
        novel_id = uuid.uuid4()
        chapters = [
            make_chapter(novel_id=novel_id, position=i, summary=f"Summary {i}.") for i in range(3)
        ]
        adapter = _adapter()
        registry = _RecordingModelRegistry()

        items = await build_remap_items(
            chapters,
            {},
            adapter,
            "five_act",
            _fake_composer_service(),
            cast("ModelRegistry", registry),
            None,
        )

        five_act_stages = {"exposition", "rising-action", "climax", "falling-action", "resolution"}
        assert all(item.new_stage in five_act_stages for item in items)
        assert registry.prepare_calls == []

    async def test_heuristic_when_model_build_fails(self) -> None:
        from narrare_core.shared.errors import ConfigurationError

        novel_id = uuid.uuid4()
        chapters = [
            make_chapter(novel_id=novel_id, position=i, summary=f"Summary {i}.") for i in range(3)
        ]
        adapter = _adapter()
        registry = _RecordingModelRegistry(error=ConfigurationError("no provider"))

        items = await build_remap_items(
            chapters,
            {},
            adapter,
            "five_act",
            _fake_composer_service(),
            cast("ModelRegistry", registry),
            _user_config(),
        )

        five_act_stages = {"exposition", "rising-action", "climax", "falling-action", "resolution"}
        assert all(item.new_stage in five_act_stages for item in items)

    async def test_heuristic_when_coverage_below_threshold(self) -> None:
        novel_id = uuid.uuid4()
        chapters = [
            make_chapter(novel_id=novel_id, position=0, summary="Only one."),
            make_chapter(novel_id=novel_id, position=1, summary=""),
            make_chapter(novel_id=novel_id, position=2, summary=""),
        ]
        adapter = _adapter()
        registry = _RecordingModelRegistry()

        await build_remap_items(
            chapters,
            {},
            adapter,
            "five_act",
            _fake_composer_service(),
            cast("ModelRegistry", registry),
            _user_config(),
        )

        assert registry.prepare_calls == []


class TestServiceRemapAgentWiring:
    """StoryboardService threads routing + credentials into the remap path."""

    @pytest.fixture
    def novel_repo(self) -> FakeNovelRepository:
        return FakeNovelRepository()

    @pytest.fixture
    def chapter_repo(self) -> FakeChapterRepository:
        return FakeChapterRepository()

    async def test_preview_remap_threads_registry_and_credentials(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
    ) -> None:
        novel_id, user_id = _seed_novel(novel_repo, story_structure="three_act")
        _seed_chapters(chapter_repo, novel_id, 3, with_summaries=True)
        registry = _RecordingModelRegistry()
        config = _user_config()
        service = StoryboardService(
            outline_repo=FakeOutlineRepository(),
            chapter_repo=chapter_repo,
            novel_repo=novel_repo,
            ai_remap_service=_fake_composer_service(),
            model_registry=cast("ModelRegistry", registry),
            model_config=config,
            api_key="sk-user-key",
            base_url="https://user.example/v1",
        )

        await service.preview_remap(novel_id, "five_act", user_id)

        assert len(registry.prepare_calls) == 1
        call = registry.prepare_calls[0]
        assert call["config"] is config
        assert call["intent"] is LLMIntent.PLAN
        assert call["usage_limits"] is not None
        assert call["api_key"] == "sk-user-key"
        assert call["base_url"] == "https://user.example/v1"

    async def test_preview_remap_without_ai_service_never_resolves_model(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
    ) -> None:
        novel_id, user_id = _seed_novel(novel_repo, story_structure="three_act")
        _seed_chapters(chapter_repo, novel_id, 3, with_summaries=True)
        registry = _RecordingModelRegistry()
        service = StoryboardService(
            outline_repo=FakeOutlineRepository(),
            chapter_repo=chapter_repo,
            novel_repo=novel_repo,
            model_registry=cast("ModelRegistry", registry),
            model_config=_user_config(),
        )

        await service.preview_remap(novel_id, "five_act", user_id)

        assert registry.prepare_calls == []
