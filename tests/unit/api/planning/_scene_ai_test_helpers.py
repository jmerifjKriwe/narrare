"""Shared SceneAIService test fakes + builders (PLAN-001 T8).

Extracted from ``test_scene_ai_service.py`` for the 400-line test-file
limit (RULE-04) — consumed by the service behaviour modules.
FunctionModel-backed seams (no LLM, RULE-01b); TestModel is avoided for
structured outputs (T6 carry-forward: it auto-generates empty lists —
use FunctionModel ``final_result`` tool calls).
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from narrare.planning.schemas_scenes import (
    SceneDraftRequest,
    SceneRefineRequest,
)
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.prompts.composer import ComposedPrompt
from narrare_core.shared.errors import ConfigurationError
from tests.unit.api.planning._scene_service_test_helpers import _World

if TYPE_CHECKING:
    from narrare_core.llm.intents import LLMIntent
    from tests.fakes import FakeChapterRepository, FakeNovelRepository

# ---------------------------------------------------------------------------
# Fakes (RULE-23 — real implementations, no MagicMocks for domain deps)
# ---------------------------------------------------------------------------

_CONFIG = ResolvedModelConfig(provider_name="zai", model_id="glm-4.7", temperature=0.7)


def _resolved_model() -> ResolvedModel:
    return ResolvedModel(config=_CONFIG, api_key=None, base_url=None, source="unit-test")


class RecordingResolution:
    """Fake ``ModelResolution`` — records resolve() calls, canned outcome.

    ``result=None`` simulates the no-provider cascade outcome
    (``ConfigurationError``) for the graceful-degradation nodes.
    """

    def __init__(self, result: ResolvedModel | None = None) -> None:
        self._result = result
        self.calls = 0

    async def resolve(self) -> ResolvedModel:
        self.calls += 1
        if self._result is None:
            raise ConfigurationError("No AI provider configured.", code="NO_AI_PROVIDER")
        return self._result


class FakeComposer:
    """Fake PromptComposer — records build() calls; marker system prompt.

    The ``SYSTEM[<mode>]`` marker lets tests assert the composed system
    prompt reaches the agent constructor (channel separation) and that the
    governed mode was requested through the composer cascade.
    """

    def __init__(self) -> None:
        self.build_calls: list[tuple[LLMIntent, str]] = []

    async def build(self, intent: LLMIntent, context: Any, **_kw: Any) -> ComposedPrompt:
        self.build_calls.append((intent, context.mode))
        return ComposedPrompt(system=f"SYSTEM[{context.mode}]", user="")


class RecordingModelRegistry:
    """Async fake ModelRegistry — FunctionModel seam that captures run prompts.

    ``respond`` maps the captured run prompt to a structured ``ModelResponse``
    (T6 ``final_result`` tool-call pattern). Captured prompts enable the
    XML-wrapping / rendered-scene assertions.
    """

    def __init__(self, respond: Any) -> None:
        self._respond = respond
        self.prepare_calls = 0
        self.run_prompts: list[str] = []

    def _handler(self, messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        self.run_prompts.append(_last_user_text(messages))
        return self._respond()

    async def prepare(self, _config: Any, **_kw: Any) -> Any:
        self.prepare_calls += 1
        from types import SimpleNamespace

        model = FunctionModel(self._handler)
        return SimpleNamespace(model=model, model_settings=None, usage_limits=None)


def _last_user_text(messages: list[ModelMessage]) -> str:
    """Extract the run prompt (last user channel text) from a message history."""
    for message in reversed(messages):
        if isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, UserPromptPart):
                    return str(part.content)
    return ""


def _draft_response(scenes: list[dict[str, Any]]) -> ModelResponse:
    return ModelResponse(
        parts=[ToolCallPart(tool_name="final_result", args=json.dumps({"scenes": scenes}))]
    )


def _refine_response(scene: dict[str, Any]) -> ModelResponse:
    return ModelResponse(
        parts=[ToolCallPart(tool_name="final_result", args=json.dumps({"scene": scene}))]
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_service(
    *,
    resolution: RecordingResolution,
    composer: FakeComposer,
    registry: RecordingModelRegistry,
    novel_repo: FakeNovelRepository,
    chapter_repo: FakeChapterRepository,
) -> Any:
    from narrare.planning.scene_ai_service import SceneAIService

    return SceneAIService(
        chapter_repo,
        novel_repo,
        registry,  # type: ignore[arg-type]
        model_resolution=resolution,
        composer=composer,  # type: ignore[arg-type]
    )


class _AiWorld(_World):
    """Seeded world + the wired SceneAIService seam set (no scene repo —
    the unused injection was removed; zero-write is source-guarded)."""

    def __init__(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
    ) -> None:
        super().__init__(novel_repo, chapter_repo)
        self.novel_repo = novel_repo
        self.chapter_repo = chapter_repo
        self.composer = FakeComposer()
        self.resolution = RecordingResolution(_resolved_model())
        self.registry = RecordingModelRegistry(lambda: _draft_response([_PROPOSED_SCENE]))

    def service(self) -> Any:
        return _make_service(
            resolution=self.resolution,
            composer=self.composer,
            registry=self.registry,
            novel_repo=self.novel_repo,
            chapter_repo=self.chapter_repo,
        )


_PROPOSED_SCENE: dict[str, Any] = {
    "title": "The Ambush at the Gate",
    "pov_character_name": "John Smith",
    "location_name": "The Castle",
    "present_characters": [{"name": "John Smith", "goal": "wants to warn the guard"}],
    "purpose": "John must reach the gate before dawn.",
    "conflict": "Mara blocks the path.",
    "resolution": "John talks his way past but at a cost.",
    "beats": ["John reaches the gate", "The horn sounds"],
}


def _draft_request(**overrides: Any) -> SceneDraftRequest:
    fields: dict[str, Any] = {
        "structure_type": "three_act",
        "outline_notes": "Escape sequence.",
        "chapter_summary": "John races to the gate.",
        "neighbor_summaries": "Prev: John flees. Next: The gate falls.",
        "instruction": "Plan 3 tense scenes.",
        "scene_count": 3,
    }
    fields.update(overrides)
    return SceneDraftRequest(**fields)


def _refine_request(**overrides: Any) -> SceneRefineRequest:
    fetched = _payload_scene()
    fields: dict[str, Any] = {
        "scene": fetched,
        "prev_scene_summary": "John flees the city.",
        "next_scene_summary": "The gate falls.",
        "chapter_summary": "John races to the gate.",
        "instruction": "Make the conflict sharper.",
    }
    fields.update(overrides)
    return SceneRefineRequest(**fields)


def _payload_scene(**overrides: Any) -> Any:
    """Full SceneSchema payload for the refine request (timestamps required)."""
    from datetime import UTC, datetime

    from narrare.planning.schemas_scenes import SceneSchema

    now = datetime.now(UTC)
    fields: dict[str, Any] = {
        "id": overrides.pop("id", uuid.uuid4()),
        "position": overrides.pop("position", 2),
        "title": "The Ambush at the Gate",
        "pov_character_ref": None,
        "location_ref": None,
        "present_characters": [],
        "purpose": "John must reach the gate before dawn.",
        "conflict": "Mara blocks the path.",
        "resolution": "John talks his way past.",
        "beats": ["John reaches the gate"],
        "status": "planned",
        "created_at": now,
        "updated_at": now,
    }
    fields.update(overrides)
    return SceneSchema(**fields)
