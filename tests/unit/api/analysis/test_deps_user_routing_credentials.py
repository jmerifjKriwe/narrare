"""User-routing migration tests — credentials reach the resolution point (Task 2a).

Companion of ``test_deps_user_routing.py`` (split off for the RULE-04
test-file hard limit). Proves that the api_key/base_url resolved by the
per-user cascade reach the ACTUAL resolution calls inside the services
(the setup-bug shape fixed like Task 1a):

- ``ReadabilityService._get_agent`` (ANALYSE)
- ``POVService._get_agent`` (ANALYSE)
- ``BetaReaderService.analyze`` (BETA_READ)
- ``run_character_voice_agent`` (VOICE)
- ``CoreferenceService.analyze`` (ANALYSE)

Same conventions as the sibling files: fake resolver, cast-pattern
registry fakes (mirrors ``test_deps_user_routing.py``, Task 1a).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare_core.llm import ResolvedModelConfig
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from narrare_core.llm.gateway import ModelRegistry

# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_deps_user_routing.py, Task 1a conventions)
# ---------------------------------------------------------------------------

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


class _StopResolution(Exception):
    """Sentinel raised after get_model recorded its call (short-circuits run)."""


class _RecordingRegistry:
    """Fake ModelRegistry — records ``get_model`` calls for assertions."""

    def __init__(self, stop_after_record: BaseException | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self._stop = stop_after_record

    async def get_model(
        self,
        config: ResolvedModelConfig,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        usage_limits: object = None,
    ) -> object:
        self.calls.append({"config": config, "api_key": api_key, "base_url": base_url})
        if self._stop is not None:
            raise self._stop
        return SimpleNamespace(sentinel_model=True)


# ===========================================================================
# Resolution point — credentials reach ModelRegistry.get_model
# ===========================================================================


class TestCredentialsReachResolutionPoint:
    """The resolved key must flow into the ACTUAL get_model call (setup bug)."""

    async def test_readability_service_threads_credentials_into_get_model(self) -> None:
        from narrare.analysis.services.readability_service import ReadabilityService

        config = _user_config()
        registry = _RecordingRegistry(stop_after_record=_StopResolution())
        service = ReadabilityService(
            chapter_repo=MagicMock(spec=True, name="ChapterRepository"),
            novel_repo=MagicMock(spec=True, name="NovelRepository"),
            model_registry=cast("ModelRegistry", registry),
            model_config=config,
            composer=MagicMock(spec=True, name="PromptComposer"),
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )

        with pytest.raises(_StopResolution):
            await service._get_agent(system_prompt="system prompt")

        assert registry.calls == [
            {"config": config, "api_key": _USER_KEY, "base_url": _USER_BASE_URL}
        ]

    async def test_pov_service_threads_credentials_into_get_model(self) -> None:
        from narrare.analysis.services.pov_service import POVService

        config = _user_config()
        registry = _RecordingRegistry(stop_after_record=_StopResolution())
        service = POVService(
            chapter_repo=MagicMock(spec=True, name="ChapterRepository"),
            novel_repo=MagicMock(spec=True, name="NovelRepository"),
            kb_repo=MagicMock(spec=True, name="KBRepository"),
            model_registry=cast("ModelRegistry", registry),
            model_config=config,
            composer=MagicMock(spec=True, name="PromptComposer"),
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )

        with pytest.raises(_StopResolution):
            await service._get_agent(system_prompt="system prompt")

        assert registry.calls == [
            {"config": config, "api_key": _USER_KEY, "base_url": _USER_BASE_URL}
        ]

    async def test_beta_reader_service_threads_credentials_into_get_model(self) -> None:
        from narrare.analysis.beta_reader_service import BetaReaderService
        from narrare.analysis.schemas import BetaReaderRequest

        config = _user_config()
        registry = _RecordingRegistry(stop_after_record=_StopResolution())
        assembler = MagicMock(spec=["build_context"], name="ContextAssembler")
        assembler.build_context = AsyncMock(
            return_value=SimpleNamespace(
                chapter_text="A long chapter text.",
                word_count=1500,
                language="en",
                focus_categories=[],
            )
        )
        cache = MagicMock(spec=["get", "set"], name="BetaReaderCache")
        cache.get = AsyncMock(return_value=None)
        composer = MagicMock(spec=["build"], name="PromptComposer")
        composer.build = AsyncMock(
            return_value=ComposedPrompt(system="system prompt", user="user prompt")
        )

        service = BetaReaderService(
            context_assembler=assembler,
            cache=cache,
            registry=cast("ModelRegistry", registry),
            config=config,
            composer=composer,
            invocation_pipeline=None,
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )

        with pytest.raises(_StopResolution):
            await service.analyze(
                novel_id=uuid4(),
                user_id=uuid4(),
                request=BetaReaderRequest(chapter_ids=[str(uuid4())]),
            )

        assert registry.calls == [
            {"config": config, "api_key": _USER_KEY, "base_url": _USER_BASE_URL}
        ]

    async def test_character_voice_runner_threads_credentials_into_get_model(self) -> None:
        from narrare.analysis.character_voice_agent_runner import run_character_voice_agent

        config = _user_config()
        registry = _RecordingRegistry(stop_after_record=_StopResolution())

        with pytest.raises(_StopResolution):
            await run_character_voice_agent(
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

        assert registry.calls == [
            {"config": config, "api_key": _USER_KEY, "base_url": _USER_BASE_URL}
        ]

    async def test_coreference_service_threads_credentials_into_get_model(self) -> None:
        from narrare.analysis.coreference_service import CoreferenceService

        config = _user_config()
        registry = _RecordingRegistry(stop_after_record=_StopResolution())
        chapter_repo = MagicMock(spec=["get"], name="ChapterRepository")
        chapter_repo.get = AsyncMock(
            return_value=SimpleNamespace(novel_id=uuid4(), content="Some text.", title="Ch 1")
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
            model_config=config,
            composer=composer,
            kb_context_provider=None,
            invocation_pipeline=None,
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )

        with pytest.raises(_StopResolution):
            async for _ in service.analyze(chapter_id=uuid4(), user_id=uuid4()):
                pass

        assert registry.calls == [
            {"config": config, "api_key": _USER_KEY, "base_url": _USER_BASE_URL}
        ]
