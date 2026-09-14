"""User-routing migration tests — series credentials reach the resolution point.

Split off ``test_deps_user_routing_factories.py`` for the RULE-04
test-file hard limit (mirrors the analysis-domain sibling split:
``test_deps_user_routing_credentials.py``). Proves that the api_key/
base_url resolved by the per-user cascade reach the services' ACTUAL
resolution calls:

- ``SeriesVoiceService.profile_from_novel`` (VOICE)
- ``SeriesConsistencyService.check_novel`` (ANALYSE)
- ``SeriesVoiceDriftService.check`` (VOICE)

Task-6a note: the shared author-voice runner now resolves via
``ModelRegistry.prepare``; the ``_RecordingRegistry.prepare`` bridge
delegates to the same recording ``get_model`` call, so these credential
assertions hold unchanged for both the migrated (prepare) and
not-yet-migrated (direct get_model) paths under test.

Same conventions as the sibling files: fake resolver, cast-pattern
registry fakes.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from narrare._app.dependencies_services import StaticModelResolution
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel

if TYPE_CHECKING:
    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.series.contracts import SeriesRepositoryProtocol
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

# ---------------------------------------------------------------------------
# Shared helpers (mirrors the sibling factories-file conventions)
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


class _StopResolution(BaseException):
    """Sentinel raised after get_model recorded its call (short-circuits run).

    ``BaseException`` (not ``Exception``) so the services' broad
    ``except Exception`` error wrappers (RULE-11) cannot swallow it into a
    ``WritingError``.
    """


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

    async def prepare(
        self,
        config: ResolvedModelConfig,
        *,
        intent: object = None,
        usage_limits: object = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> object:
        """Task-6a bridge: resolution flows through prepare → get_model.

        Delegates to the SAME recording ``get_model`` call so the
        credential assertions (``registry.calls`` shape) hold for both
        the migrated (prepare) and not-yet-migrated (direct get_model)
        paths under test.
        """
        return SimpleNamespace(
            model=await self.get_model(config, api_key=api_key, base_url=base_url),
            model_settings=None,
            usage_limits=usage_limits,
        )


# ===========================================================================
# Resolution point — credentials reach the services' ACTUAL get_model calls
# ===========================================================================


class TestSeriesCredentialsReachResolutionPoint:
    """The resolved key must flow into each service's ACTUAL get_model call."""

    async def test_series_voice_service_threads_credentials_into_get_model(self) -> None:
        from narrare.series.series_voice_service import SeriesVoiceService
        from tests.fakes.fake_chapter_repo import FakeChapterRepository
        from tests.fakes.fake_novel_repo import FakeNovelRepository
        from tests.fakes.fake_series_repo import FakeSeriesRepository

        from ._series_voice_drift_test_helpers import seed_owned_series
        from ._series_voice_test_helpers import patch_author_voice_pipeline

        user_id = uuid4()
        series_repo, novel_repo, chapter_repo = (
            FakeSeriesRepository(),
            FakeNovelRepository(),
            FakeChapterRepository(),
        )
        series_id, novel_id = seed_owned_series(
            series_repo,
            novel_repo,
            chapter_repo,
            user_id=user_id,
        )

        config = _user_config()
        registry = _RecordingRegistry(stop_after_record=_StopResolution())
        service = SeriesVoiceService(
            series_repo=cast("SeriesRepositoryProtocol", series_repo),
            novel_repo=cast("NovelRepositoryProtocol", novel_repo),
            chapter_repo=cast("ChapterRepositoryProtocol", chapter_repo),
            model_registry=cast("ModelRegistry", registry),
            model_resolution=StaticModelResolution(
                ResolvedModel(
                    config=config,
                    api_key=_USER_KEY,
                    base_url=_USER_BASE_URL,
                    source="unit-test",
                )
            ),
            composer=cast("PromptComposer", MagicMock(spec=["build"], name="PromptComposer")),
        )

        # get_model raises the sentinel through the (real) shared agent runner
        # — proving the credentials travel factory → service → get_model.
        with patch_author_voice_pipeline(), pytest.raises(_StopResolution):
            await service.profile_from_novel(series_id, novel_id, user_id)

        assert registry.calls == [
            {"config": config, "api_key": _USER_KEY, "base_url": _USER_BASE_URL}
        ]

    async def test_series_consistency_service_threads_credentials_into_get_model(self) -> None:
        from narrare.series.series_consistency_service import SeriesConsistencyService
        from tests.fakes.fake_chapter_repo import FakeChapterRepository
        from tests.fakes.fake_kb_scope_repo import FakeScopeKBRepo
        from tests.fakes.fake_novel_repo import FakeNovelRepository
        from tests.fakes.fake_series_repo import FakeSeriesRepository

        from ._series_consistency_test_helpers import (
            FakeSeriesConsistencyComposer,
            seed_owned_series_with_canon,
        )

        user_id = uuid4()
        series_repo, novel_repo, chapter_repo = (
            FakeSeriesRepository(),
            FakeNovelRepository(),
            FakeChapterRepository(),
        )
        kb_repo = FakeScopeKBRepo()
        series_id, novel_id = seed_owned_series_with_canon(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            user_id=user_id,
        )

        config = _user_config()
        registry = _RecordingRegistry(stop_after_record=_StopResolution())
        service = SeriesConsistencyService(
            series_repo=cast("SeriesRepositoryProtocol", series_repo),
            novel_repo=cast("NovelRepositoryProtocol", novel_repo),
            chapter_repo=cast("ChapterRepositoryProtocol", chapter_repo),
            kb_repo=cast("KBRepositoryProtocol", kb_repo),
            registry=cast("ModelRegistry", registry),
            model_resolution=StaticModelResolution(
                ResolvedModel(
                    config=config,
                    api_key=_USER_KEY,
                    base_url=_USER_BASE_URL,
                    source="unit-test",
                )
            ),
            composer=cast("PromptComposer", FakeSeriesConsistencyComposer()),
        )

        # The sentinel escapes the service's broad RULE-11 error wrapper
        # (BaseException) — proving the credentials reach the real get_model.
        with pytest.raises(_StopResolution):
            await service.check_novel(series_id, novel_id, user_id)

        assert registry.calls == [
            {"config": config, "api_key": _USER_KEY, "base_url": _USER_BASE_URL}
        ]

    async def test_series_voice_drift_service_threads_credentials_into_get_model(self) -> None:
        from narrare.analysis.schemas_author_voice_drift import AuthorVoiceDriftRequest
        from narrare.series.series_voice_drift_service import SeriesVoiceDriftService
        from tests.fakes.fake_chapter_repo import FakeChapterRepository
        from tests.fakes.fake_novel_repo import FakeNovelRepository
        from tests.fakes.fake_series_repo import FakeSeriesRepository

        from ._series_voice_drift_test_helpers import (
            make_author_profile,
            patch_mode1,
            seed_owned_series,
            seed_series_voice,
        )

        user_id = uuid4()
        series_repo, novel_repo, chapter_repo = (
            FakeSeriesRepository(),
            FakeNovelRepository(),
            FakeChapterRepository(),
        )
        series_id, novel_id = seed_owned_series(
            series_repo,
            novel_repo,
            chapter_repo,
            user_id=user_id,
        )
        await seed_series_voice(series_repo, series_id, make_author_profile())

        config = _user_config()
        registry = _RecordingRegistry(stop_after_record=_StopResolution())
        service = SeriesVoiceDriftService(
            series_repo=cast("SeriesRepositoryProtocol", series_repo),
            novel_repo=cast("NovelRepositoryProtocol", novel_repo),
            chapter_repo=cast("ChapterRepository", chapter_repo),
            model_registry=cast("ModelRegistry", registry),
            model_resolution=StaticModelResolution(
                ResolvedModel(
                    config=config,
                    api_key=_USER_KEY,
                    base_url=_USER_BASE_URL,
                    source="unit-test",
                )
            ),
            composer=cast("PromptComposer", MagicMock(spec=["build"], name="PromptComposer")),
        )

        with patch_mode1(), pytest.raises(_StopResolution):
            await service.check(series_id, novel_id, user_id, AuthorVoiceDriftRequest())

        assert registry.calls == [
            {"config": config, "api_key": _USER_KEY, "base_url": _USER_BASE_URL}
        ]
