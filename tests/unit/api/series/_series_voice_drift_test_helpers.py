"""Shared fakes + fixtures for SeriesVoiceDriftService unit tests (ADR-030).

The series-voice-drift service REUSES the novel-level analysis pipeline
(:func:`compute_author_voice_per_chapter`, :func:`analyse_author_voice_drift`,
:func:`resolve_author_voice_drift_prompt`), so this helper REUSES the
novel-level drift test helpers
(:mod:`tests.unit.api.analysis._author_voice_drift_test_helpers`) for:

- :func:`make_author_profile` — builds an :class:`AuthorVoiceProfile` with the
  voice + author metric blocks the trend needs (or without them, to exercise
  the graceful ``no_series_voice_metrics`` path).
- :func:`patch_mode1` — patches ``AuthorVoiceDriftAgent`` +
  ``compose_invocation`` (Mode 1) — the exact seam the reused pipeline hits.
- :func:`make_drift_result` — a fake agent classification output.

Only the series-specific wiring (FakeSeriesRepository carrying the series voice
profile in ``SeriesSettings.author_voice``) is new here.

Mirrors ``_series_voice_test_helpers.py`` (the Spec 3 profiling parallel) +
``_author_voice_drift_test_helpers.py`` (the novel-level drift parallel).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock

from narrare._app.dependencies_services import StaticModelResolution
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.prompts.composer import ComposedPrompt
from tests.fakes.fake_chapter_repo import FakeChapterRepository
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository

# Reuse the novel-level drift helpers verbatim (the pipeline is shared).
# NOTE: ``_SAMPLE_PROSE`` is private in the analysis helper, so this module
# defines its own ``SAMPLE_PROSE`` constant (same prose, public name).
#
# Two non-obvious choices here, both required to satisfy pyright:
#
# 1. RELATIVE import (``..analysis``), not the absolute
#    ``tests.unit.api.analysis._author_voice_drift_test_helpers``. Under
#    ``tests/pyrightconfig.json`` the ``tests`` package is not guaranteed to
#    resolve as an absolute top-level package, and ``reportMissingImports: false``
#    would mask that failure — leaving the imported names Unknown so downstream
#    ``from _series_voice_drift_test_helpers import make_author_profile`` gets
#    flagged "unknown import symbol". A relative import resolves via the package
#    layout (no sys.path needed), exactly like the novel-level analysis tests.
#
# 2. ``__all__`` declares the three re-exported names. Pyright does not honor
#    ruff's ``F401`` suppression for re-export detection, so a bare
#    ``from x import name`` is treated as a private import and the consumer
#    test module's import is flagged "unknown import symbol". Listing the names
#    in ``__all__`` marks them as exported for both pyright and ruff (ruff then
#    also treats them as used, so no F401).
from ..analysis._author_voice_drift_test_helpers import (
    make_author_profile,
    make_drift_result,
    patch_mode1,
)

__all__ = [
    "make_author_profile",
    "make_drift_result",
    "patch_mode1",
]

if TYPE_CHECKING:
    from uuid import UUID

    from pydantic_ai.usage import UsageLimits

    from narrare.chapters.repository import ChapterRepository
    from narrare.series.series_voice_drift_service import SeriesVoiceDriftService
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.profiles.author_voice import AuthorVoiceProfile

#: Real narrator prose (>=1 chapter) so the deterministic metric analyzers
#: produce non-None VoiceMetrics / AuthorMetrics (mirrors the novel-level
#: helper's private ``_SAMPLE_PROSE``).
SAMPLE_PROSE = (
    "The wind moved through the long grass like a rumour, carrying the "
    "scent of distant rain. She paused at the threshold, weighing the cost "
    'of every word. "You came," she said quietly. The evening deepened '
    "around them, patient and full of unspoken things."
)


class _FakeComposer:
    """Minimal PromptComposer fake (DI wiring only — compose is patched)."""

    def __init__(self) -> None:
        self.build = AsyncMock(
            return_value=ComposedPrompt(system="COMPOSED-AUTHOR-VOICE-DRIFT-SYSTEM", user="")
        )


class _FakeModelRegistry:
    """Fake ModelRegistry returning a stub Model.

    ``prepare`` mirrors the real single assembly point (Task 4): exactly
    one ``get_model`` resolution, a canned sentinel ``model_settings``
    (so pass-through to ``agent.run`` is assertable), and the
    ``usage_limits`` pass-through. Mirrors the analysis-domain
    ``FakeModelRegistry`` fakes (Task 6a).
    """

    def __init__(self) -> None:
        self.get_model = AsyncMock(return_value=MagicMock(spec=object))
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


def make_config() -> ResolvedModelConfig:
    """A default ``ResolvedModelConfig`` for SeriesVoiceDriftService tests."""
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


def make_composer() -> _FakeComposer:
    """A minimal PromptComposer fake for SeriesVoiceDriftService tests."""
    return _FakeComposer()


def make_resolved_model(
    config: ResolvedModelConfig | None = None,
) -> ResolvedModel:
    """A fixed model triple wrapping ``make_config`` (ADR-086 seam)."""
    return ResolvedModel(
        config=config or make_config(),
        api_key=None,
        base_url=None,
        source="unit-test",
    )


def make_service(
    *,
    series_repo: FakeSeriesRepository | None = None,
    novel_repo: FakeNovelRepository | None = None,
    chapter_repo: FakeChapterRepository | None = None,
) -> tuple[
    SeriesVoiceDriftService,
    FakeSeriesRepository,
    FakeNovelRepository,
    FakeChapterRepository,
]:
    """Build a SeriesVoiceDriftService wired with fakes (agent patched per-test).

    Returns ``(service, series_repo, novel_repo, chapter_repo)`` so tests can
    seed data and assert interactions. ``chapter_repo`` is cast to the concrete
    :class:`ChapterRepository` at the boundary (the service types it concretely
    to match the novel-level parallel + ``load_selected_chapters``). The model
    triple is injected pre-resolved via ``StaticModelResolution`` (ADR-086:
    mechanical ctor migration — outcomes unchanged).
    """
    from narrare.series.series_voice_drift_service import SeriesVoiceDriftService

    series_repo = series_repo or FakeSeriesRepository()
    novel_repo = novel_repo or FakeNovelRepository()
    chapter_repo = chapter_repo or FakeChapterRepository()

    service = SeriesVoiceDriftService(
        series_repo=series_repo,  # type: ignore[arg-type]
        novel_repo=novel_repo,  # type: ignore[arg-type]
        chapter_repo=cast("ChapterRepository", chapter_repo),  # type: ignore[arg-type]
        model_registry=_FakeModelRegistry(),  # type: ignore[arg-type]
        model_resolution=StaticModelResolution(make_resolved_model()),
        composer=_FakeComposer(),  # type: ignore[arg-type]
    )
    return service, series_repo, novel_repo, chapter_repo


async def seed_series_voice(
    series_repo: FakeSeriesRepository, series_id: UUID, profile: AuthorVoiceProfile | None
) -> None:
    """Store (or clear) the series voice profile in ``SeriesSettings``.

    Mirrors how ``SeriesVoiceService.profile_from_novel`` persists: a
    ``model_dump(mode="json")`` of the :class:`AuthorVoiceProfile`. Pass
    ``None`` to leave the series without a stored voice.
    """
    if profile is not None:
        await series_repo.update_settings(
            series_id, {"author_voice": profile.model_dump(mode="json")}
        )


def seed_owned_series(
    series_repo: FakeSeriesRepository,
    novel_repo: FakeNovelRepository,
    chapter_repo: FakeChapterRepository,
    *,
    user_id: UUID,
    chapter_count: int = 2,
) -> tuple[UUID, UUID]:
    """Seed an owned series + one member novel with prose chapters.

    Returns ``(series_id, novel_id)``. Shared across the voice-drift test
    classes to keep the test module under the RULE-04 limit.
    """
    import uuid as _uuid

    from narrare_core.series.schemas import Series
    from tests.factories import make_chapter, make_novel

    series_id = _uuid.uuid4()
    novel_id = _uuid.uuid4()
    series_repo.seed(
        Series(id=series_id, user_id=user_id, title="The Expanse", writing_language="en")
    )
    novel_repo.seed(
        make_novel(id=novel_id, user_id=user_id, series_id=series_id, title="Leviathan Wakes")
    )
    chapter_repo.seed(
        *[
            make_chapter(novel_id=novel_id, position=i, content=SAMPLE_PROSE)
            for i in range(1, chapter_count + 1)
        ]
    )
    return series_id, novel_id
