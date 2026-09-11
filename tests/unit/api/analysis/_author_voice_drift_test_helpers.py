"""Shared test helpers for ANAL-009 Phase 2B author-voice-drift service tests.

Mirrors ``_voice_drift_test_helpers.py`` (Phase 1 per-character drift) +
``_author_voice_test_helpers.py`` (Phase 2A author profiling). The author-
drift service is a read-only consumer of the stored
:class:`AuthorVoiceProfile` via :class:`AuthorVoiceRepository` (ADR-074 — no
direct column access), so the repository fake exposes ``load`` with a seedable
profile. The service is novel-scoped and needs MULTIPLE chapters (for the
longitudinal trend + jumps), so the chapter repository fake supports
``list_by_novel`` + ``get_by_id``.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch

from narrare.analysis.author_voice_drift_service import AuthorVoiceDriftService
from narrare_core.agents.character_voice_drift_types import VoiceDriftResult
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from pydantic_ai.usage import UsageLimits

    from narrare.analysis.author_voice_repository import AuthorVoiceRepository
    from narrare.analysis.schemas_author_voice_drift import AuthorVoiceDriftEvent
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.llm.model_config import ResolvedModelConfig
    from narrare_core.profiles.author_voice import AuthorVoiceProfile
    from narrare_core.prompts.composer import PromptComposer


@dataclass(frozen=True)
class FakeNovel:
    """Minimal novel object with the attributes the service reads."""

    id: uuid.UUID
    title: str = "Test Novel"
    genre: str = "Fantasy"
    writing_language: str = "en"


@dataclass(frozen=True)
class FakeChapter:
    """Minimal chapter object with the attributes the service reads."""

    id: uuid.UUID
    novel_id: uuid.UUID
    title: str = "Chapter 1"
    content: str = ""


class FakeModelRegistry:
    """Fake ModelRegistry returning a stub model.

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


class FakeComposer:
    """Fake PromptComposer for Mode-1 DI wiring.

    The service routes through ``compose_invocation`` (which calls
    ``composer.build`` internally), so this fake only needs to exist for DI
    wiring — its ``build`` is never reached when ``compose_invocation`` is
    patched. Kept as a real object (not a bare MagicMock) so the service's
    ``composer is None`` guard is satisfied.
    """

    def __init__(self) -> None:
        self.build: AsyncMock = AsyncMock(
            return_value=ComposedPrompt(system="COMPOSED-AUTHOR-VOICE-DRIFT-SYSTEM", user="")
        )


class FakeComposedInvocation:
    """Stand-in for a Mode-1 composed invocation."""

    def __init__(self, system: str = "COMPOSED-AUTHOR-VOICE-DRIFT-SYSTEM", user: str = "") -> None:
        self.composed_prompt = ComposedPrompt(system=system, user=user)


class FakeNovelRepository:
    """Novel repository fake with call tracking."""

    def __init__(self, novel: FakeNovel | None) -> None:
        self.novel = novel
        self.calls: list[tuple[str, uuid.UUID, uuid.UUID]] = []

    async def get_by_id(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> FakeNovel | None:
        self.calls.append(("get_by_id", novel_id, user_id))
        return self.novel


class FakeChapterRepository:
    """Chapter repository fake supporting list_by_novel + get_by_id."""

    def __init__(self, chapters: list[FakeChapter]) -> None:
        self._chapters = chapters
        self.list_calls: list[uuid.UUID] = []
        self.get_calls: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def list_by_novel(
        self, novel_id: uuid.UUID, volume_id: uuid.UUID | None = None
    ) -> list[FakeChapter]:
        self.list_calls.append(novel_id)
        return [ch for ch in self._chapters if ch.novel_id == novel_id]

    async def get_by_id(self, chapter_id: uuid.UUID, novel_id: uuid.UUID) -> FakeChapter | None:
        self.get_calls.append((chapter_id, novel_id))
        return next(
            (ch for ch in self._chapters if ch.id == chapter_id and ch.novel_id == novel_id),
            None,
        )


class FakeAuthorVoiceRepository:
    """Fake AuthorVoiceRepository — records load calls; seed a profile.

    The drift service is read-only (ADR-073 D5) and only calls ``load``; the
    ``save`` / ``clear`` methods are implemented so the fake is a drop-in for
    any future caller and so tests can assert the drift service never mutates
    storage.
    """

    def __init__(self, profile: AuthorVoiceProfile | None = None) -> None:
        self._profile = profile
        self.load_calls: list[uuid.UUID] = []
        self.save_calls: list[tuple[uuid.UUID, object]] = []
        self.clear_calls: list[uuid.UUID] = []

    async def load(self, novel_id: uuid.UUID) -> AuthorVoiceProfile | None:
        self.load_calls.append(novel_id)
        return self._profile

    async def save(self, novel_id: uuid.UUID, profile: object) -> None:
        self.save_calls.append((novel_id, profile))

    async def clear(self, novel_id: uuid.UUID) -> None:
        self.clear_calls.append(novel_id)


async def consume(
    stream: AsyncIterator[AuthorVoiceDriftEvent],
) -> list[AuthorVoiceDriftEvent]:
    """Collect all events from the service async generator."""
    return [event async for event in stream]


def make_novel(**overrides: object) -> FakeNovel:
    """Build a novel fixture."""
    return FakeNovel(
        id=cast("uuid.UUID", overrides.get("id", uuid.uuid4())),
        title=str(overrides.get("title", "Test Novel")),
        genre=str(overrides.get("genre", "Fantasy")),
        writing_language=str(overrides.get("writing_language", "en")),
    )


def make_chapter(**overrides: object) -> FakeChapter:
    """Build a chapter fixture with narrator prose."""
    return FakeChapter(
        id=cast("uuid.UUID", overrides.get("id", uuid.uuid4())),
        novel_id=cast("uuid.UUID", overrides.get("novel_id", uuid.uuid4())),
        title=str(overrides.get("title", "Chapter 1")),
        content=str(overrides.get("content", _SAMPLE_PROSE)),
    )


def make_author_profile(
    *,
    with_metrics: bool = True,
) -> AuthorVoiceProfile:
    """Build a stored author-voice profile with deterministic metrics.

    Args:
        with_metrics: When ``True`` (default) the profile carries BOTH the
            voice-generic ``voice_metrics`` block AND the author-specific
            ``author_metrics`` block (the trend comparison needs both). When
            ``False`` the profile is missing both (exercises the
            ``no_profile_metrics`` graceful path).
    """
    from narrare_core.analysis.author_metrics import AuthorMetrics
    from narrare_core.kb.schemas.character import VoiceMetrics
    from narrare_core.profiles.author_voice import AuthorVoiceProfile
    from narrare_core.schemas.voice import VoiceAnalysis

    if with_metrics:
        voice_analysis = VoiceAnalysis(
            formality=0.6,
            vocabulary_level="complex",
            voice_metrics=VoiceMetrics(
                avg_sentence_length=12.0,
                sentence_length_std=2.5,
                type_token_ratio=0.7,
                avg_syllables_per_word=1.5,
                contraction_rate=0.1,
            ),
        )
        author_metrics = AuthorMetrics(
            dialogue_ratio=0.4,
            description_density=0.3,
            action_introspection_ratio=0.5,
            metaphor_density=0.1,
        )
    else:
        # Profile present but missing the metric blocks the trend needs.
        voice_analysis = VoiceAnalysis(formality=0.6, vocabulary_level="complex")
        author_metrics = None

    return AuthorVoiceProfile(
        voice_analysis=voice_analysis,
        author_metrics=author_metrics,
        author_examples=["The wind moved through the long grass like a rumour."],
    )


def make_drift_result(
    drift_type: str = "evolution",
    confidence: float = 0.7,
) -> VoiceDriftResult:
    """Build a fake AuthorVoiceDriftAgent output (reused VoiceDriftResult)."""
    return VoiceDriftResult(
        drift_type=drift_type,  # type: ignore[arg-type]
        confidence=confidence,
        longitudinal_reasons=["Formality declines steadily across chapters."],
        per_chapter_notes=[],
        suggested_attention=[],
    )


def make_service(
    *,
    novel: FakeNovel | None,
    chapters: list[FakeChapter],
    profile: AuthorVoiceProfile | None,
    config: ResolvedModelConfig,
    composer: FakeComposer | None = None,
) -> AuthorVoiceDriftService:
    """Build an AuthorVoiceDriftService with fakes and casts at the boundary."""
    novel_repo = FakeNovelRepository(novel)
    chapter_repo = FakeChapterRepository(chapters)
    author_voice_repo = FakeAuthorVoiceRepository(profile)

    return AuthorVoiceDriftService(
        novel_repo=cast("NovelRepository", novel_repo),
        chapter_repo=cast("ChapterRepository", chapter_repo),  # type: ignore[arg-type]
        author_voice_repo=cast("AuthorVoiceRepository", author_voice_repo),
        model_registry=cast("ModelRegistry", FakeModelRegistry()),
        model_config=config,
        composer=cast("PromptComposer", composer or FakeComposer()),
    )


@contextmanager
def patch_mode1(
    system: str = "COMPOSED-AUTHOR-VOICE-DRIFT-SYSTEM", user: str = ""
) -> Iterator[tuple[MagicMock, AsyncMock]]:
    """Patch the drift agent and Mode-1 composition function.

    Yields ``(MockAgent, mock_compose)``. The ``MockAgent`` constructor must be
    wired to a fake ``run`` by each caller.
    """
    with (
        patch(
            "narrare.analysis.author_voice_drift_agent_runner.AuthorVoiceDriftAgent"
        ) as MockAgent,
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(return_value=FakeComposedInvocation(system=system, user=user)),
        ) as mock_compose,
    ):
        yield MockAgent, mock_compose


# Two short chapters of narrator prose (narration + a little dialogue together)
# — enough for VoiceMetricsAnalyzer.analyze_text + AuthorMetricsAnalyzer.analyze
# to produce non-None metrics, and >1 chapter so the trend + jumps are
# non-trivial.
_SAMPLE_PROSE = (
    "The wind moved through the long grass like a rumour, carrying the "
    "scent of distant rain. She paused at the threshold, weighing the cost "
    'of every word. "You came," she said quietly. The evening deepened '
    "around them, patient and full of unspoken things."
)
