"""Prompt-Path-Compliance tests for SceneAIService (PLAN-001 T8, ADR-046 D.1).

Verifies that scene-plan AI prompt resolution goes through
``PromptComposer.build()`` (RULE-02b) — both governed PLAN modes — and
that chapter/scene data is passed in the run prompt (user channel), NOT
baked into the system prompt.

D.2 half of the declaration: ``check_architecture.py`` reports 0
RULE-02b violations for ``narrare.planning.scene_ai_service`` (no
inline feature-prompt assembly — the only string assembly is the
category-3 XML wrapping of runtime data in ``_scene_ai_support.py``,
RULE-22 §6).

Registry declaration: ``adoption-registry.yaml``
``prompt_path_compliance.planning/scene_plan_draft`` /
``planning/scene_plan_refine``.

See:
    ADR-046 — Prompt-Path-Compliance
    CONSTRAINTS.md RULE-02/02a/02b, RULE-11
    tests/unit/api/planning/test_timeline_prompt_path_compliance.py (precedent)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from narrare.planning.schemas_scenes import SceneDraftRequest, SceneRefineRequest
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.prompts.composer import ComposedPrompt
from tests.fakes import FakeChapterRepository, FakeNovelRepository, FakeScenePlanRepository
from tests.unit.api.planning._scene_service_test_helpers import _World

if TYPE_CHECKING:
    from collections.abc import Callable

    from narrare.planning.scene_ai_service import SceneAIService

# ---------------------------------------------------------------------------
# Fakes (RULE-TEST-01 — real fakes, no behaviour-less MagicMocks)
# ---------------------------------------------------------------------------

_CONFIG = ResolvedModelConfig(provider_name="zai", model_id="glm-4.7", temperature=0.7)

_SYSTEM_MARKER = "COMPOSED-GOVERNED-SYSTEM-PROMPT"


class RecordingComposer:
    """Fake PromptComposer — records (intent, mode) and returns a marker."""

    def __init__(self) -> None:
        self.build_calls: list[tuple[LLMIntent, str]] = []

    async def build(self, intent: LLMIntent, context: Any, **_kw: Any) -> ComposedPrompt:
        self.build_calls.append((intent, context.mode))
        return ComposedPrompt(system=_SYSTEM_MARKER, user="")


class SeamRegistry:
    """Async prepare() seam — FunctionModel capturing the run prompt."""

    def __init__(self, respond: Callable[[], ModelResponse]) -> None:
        self._respond = respond
        self.run_prompts: list[str] = []

    async def prepare(self, _config: Any, **_kw: Any) -> Any:
        from types import SimpleNamespace

        def _handler(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
            self.run_prompts.append(_last_user_text(messages))
            return self._respond()

        return SimpleNamespace(
            model=FunctionModel(_handler), model_settings=None, usage_limits=None
        )


class _StaticResolution:
    """Canned ModelResolution — the cascade outcome is not under test here."""

    async def resolve(self) -> ResolvedModel:
        return ResolvedModel(config=_CONFIG, api_key=None, base_url=None, source="unit-test")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _last_user_text(messages: list[ModelMessage]) -> str:
    """Extract the run prompt (last user-channel text) from the history."""
    from pydantic_ai.messages import UserPromptPart

    for message in reversed(messages):
        if isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, UserPromptPart):
                    return str(part.content)
    return ""


def _tool_response(payload: dict[str, Any]) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool_name="final_result", args=json.dumps(payload))])


def _carried_scene() -> Any:
    """Minimal SceneSchema payload (timestamps required by §5.1)."""
    from datetime import UTC, datetime

    from narrare.planning.schemas_scenes import SceneSchema

    now = datetime.now(UTC)
    return SceneSchema(
        id=uuid4(),
        position=1,
        title="The Ambush at the Gate",
        purpose="John must reach the gate before dawn.",
        created_at=now,
        updated_at=now,
    )


def _make_service(
    respond: Callable[[], ModelResponse],
) -> tuple[SceneAIService, SeamRegistry, _World, RecordingComposer]:
    """Build a SceneAIService with canned resolution + recording seams."""
    from narrare.planning.scene_ai_service import SceneAIService

    novel_repo = FakeNovelRepository()
    chapter_repo = FakeChapterRepository()
    world = _World(novel_repo, chapter_repo)
    composer = RecordingComposer()
    registry = SeamRegistry(respond)
    service = SceneAIService(
        FakeScenePlanRepository(),
        chapter_repo,
        novel_repo,
        registry,  # type: ignore[arg-type]
        model_resolution=_StaticResolution(),
        composer=composer,  # type: ignore[arg-type]
    )
    return service, registry, world, composer


# ---------------------------------------------------------------------------
# AC-1: both governed modes resolve via PromptComposer.build
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_draft_resolves_scene_plan_draft_mode_via_composer() -> None:
    """Draft resolves the governed ``scene_plan_draft`` PLAN mode (RULE-02b)."""
    service, _registry, world, composer = _make_service(
        lambda: _tool_response({"scenes": [{"title": "S", "purpose": "P"}]})
    )

    await service.draft(
        world.chapter_id,
        SceneDraftRequest(instruction="Plan 3 tense scenes."),
        world.user_id,
        novel_id=world.novel_id,
    )

    assert composer.build_calls == [(LLMIntent.PLAN, "scene_plan_draft")]


@pytest.mark.asyncio
async def test_refine_resolves_scene_plan_refine_mode_via_composer() -> None:
    """Refine resolves the governed ``scene_plan_refine`` PLAN mode."""
    service, _registry, world, composer = _make_service(
        lambda: _tool_response({"scene": {"title": "S", "purpose": "P"}})
    )

    await service.refine(
        world.chapter_id,
        SceneRefineRequest(scene=_carried_scene(), instruction="Make it sharper."),
        world.user_id,
        novel_id=world.novel_id,
    )

    assert composer.build_calls == [(LLMIntent.PLAN, "scene_plan_refine")]


# ---------------------------------------------------------------------------
# AC-2: channel separation — system prompt vs. run-prompt data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_composed_system_prompt_stays_out_of_the_user_channel() -> None:
    """The composed system prompt binds the agent; the run prompt stays data."""
    service, registry, world, _composer = _make_service(
        lambda: _tool_response({"scenes": [{"title": "S", "purpose": "P"}]})
    )

    await service.draft(
        world.chapter_id,
        SceneDraftRequest(chapter_summary="John races to the gate.", instruction="Go."),
        world.user_id,
        novel_id=world.novel_id,
    )

    run_prompt = registry.run_prompts[0]
    assert _SYSTEM_MARKER not in run_prompt, "system prompt leaked into the user channel"
    assert "<chapter_context>" in run_prompt
    assert "John races to the gate." in run_prompt
