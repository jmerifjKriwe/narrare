"""Shared test helpers for ANAL-009 voice-drift service tests.

Mirrors ``_voice_check_test_helpers.py`` (WRITE-010) — the drift service is a
read-only consumer of the same ``VoiceProfileConsumer`` contract, so the
fakes share the same shape. The drift service is novel-scoped and needs
MULTIPLE chapters (for the longitudinal trend + jumps), so the chapter
repository fake supports ``list_by_novel`` + ``get_by_id``.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch

from narrare.analysis.voice_drift_service import CharacterVoiceDriftService
from narrare_core.agents.character_voice_drift_types import VoiceDriftResult
from narrare_core.kb.schemas.character import VoiceMetrics
from narrare_core.profiles.models import CharacterVoiceProfile
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from narrare.analysis.schemas_voice_drift import VoiceDriftEvent
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.model_config import ResolvedModelConfig
    from narrare_core.profiles.contracts import VoiceProfileConsumer, VoiceProfileProvider
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
    """Fake ModelRegistry returning a stub model."""

    def __init__(self) -> None:
        self.get_model: AsyncMock = AsyncMock(return_value=MagicMock(spec=object))


class FakeComposer:
    """Fake PromptComposer for Mode-1 DI wiring."""

    def __init__(self) -> None:
        self.build: AsyncMock = AsyncMock(
            return_value=ComposedPrompt(system="COMPOSED-VOICE-DRIFT-SYSTEM", user="")
        )


class FakeComposedInvocation:
    """Stand-in for a Mode-1 composed invocation."""

    def __init__(self, system: str = "COMPOSED-VOICE-DRIFT-SYSTEM", user: str = "") -> None:
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


class FakeVoiceProfileConsumer:
    """VoiceProfileConsumer fake exposing only the checking projection."""

    def __init__(self, profiles: list[CharacterVoiceProfile]) -> None:
        self._profiles = profiles
        self.calls: list[tuple[str, uuid.UUID]] = []
        self.mutator_calls: list[str] = []

    @property
    def provider(self) -> VoiceProfileProvider:
        return cast("VoiceProfileProvider", object())

    async def assemble_for_generation(
        self, project_id: uuid.UUID, *, max_age_days: int = 30
    ) -> object:
        raise AssertionError("voice drift must not use the generation projection")

    async def assemble_for_checking(
        self,
        project_id: uuid.UUID,
        *,
        max_age_days: int = 30,
    ) -> list[CharacterVoiceProfile]:
        self.calls.append(("assemble_for_checking", project_id))
        return self._profiles

    async def update_voice_analysis(self) -> None:
        self.mutator_calls.append("update_voice_analysis")


async def consume(
    stream: AsyncIterator[VoiceDriftEvent],
) -> list[VoiceDriftEvent]:
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
    """Build a chapter fixture with deterministic speaker attribution."""
    return FakeChapter(
        id=cast("uuid.UUID", overrides.get("id", uuid.uuid4())),
        novel_id=cast("uuid.UUID", overrides.get("novel_id", uuid.uuid4())),
        title=str(overrides.get("title", "Chapter 1")),
        content=str(overrides.get("content", "")),
    )


def make_profile(
    name: str = "Elena",
    *,
    with_metrics: bool = True,
) -> CharacterVoiceProfile:
    """Build a stored voice profile with deterministic metrics."""
    return CharacterVoiceProfile(
        character_id=str(uuid.uuid4()),
        name=name,
        speech_summary="formal register, measured sentences, precise vocabulary",
        voice_metrics=(
            VoiceMetrics(
                avg_sentence_length=5.0,
                sentence_length_std=1.0,
                type_token_ratio=0.8,
                avg_syllables_per_word=1.4,
                contraction_rate=0.0,
                punctuation_profile={"comma": 0.2},
            )
            if with_metrics
            else None
        ),
    )


def make_drift_result(
    drift_type: str = "evolution",
    confidence: float = 0.7,
) -> VoiceDriftResult:
    """Build a fake CharacterVoiceDriftAgent output."""
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
    consumer: FakeVoiceProfileConsumer,
    config: ResolvedModelConfig,
    composer: FakeComposer | None = None,
    relationship_repo: RelationshipRepository | None = None,
) -> CharacterVoiceDriftService:
    """Build a CharacterVoiceDriftService with fakes and casts at the boundary."""
    novel_repo = FakeNovelRepository(novel)
    chapter_repo = FakeChapterRepository(chapters)

    async def consumer_provider(project_id: uuid.UUID) -> VoiceProfileConsumer:
        consumer.calls.append(("provider", project_id))
        return cast("VoiceProfileConsumer", consumer)

    return CharacterVoiceDriftService(
        novel_repo=cast("NovelRepository", novel_repo),
        chapter_repo=cast("ChapterRepository", chapter_repo),  # type: ignore[arg-type]
        model_registry=cast("ModelRegistry", FakeModelRegistry()),
        consumer_provider=consumer_provider,
        model_config=config,
        composer=cast("PromptComposer", composer or FakeComposer()),
        relationship_repo=relationship_repo,  # type: ignore[arg-type]
    )


@contextmanager
def patch_mode1(
    system: str = "COMPOSED-VOICE-DRIFT-SYSTEM", user: str = ""
) -> Iterator[tuple[MagicMock, AsyncMock]]:
    """Patch the drift agent and Mode-1 composition function."""
    with (
        patch("narrare.analysis.voice_drift_agent_runner.CharacterVoiceDriftAgent") as MockAgent,
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(return_value=FakeComposedInvocation(system=system, user=user)),
        ) as mock_compose,
    ):
        yield MockAgent, mock_compose


# Two chapters of dialogue for "Elena" with slightly different register so the
# trend + jumps are non-trivial. "Marc" speaks only in chapter 1.
CHAPTER_ONE_DIALOGUE = (
    '"One must consider the consequences," said Elena.\n'
    '"Yeah. Nope," Marc replied.\n'
    '"This is not a trivial matter," Elena said.\n'
)

CHAPTER_TWO_DIALOGUE = (
    '"Sure, whatever, it is fine," Elena said.\n"I suppose that works," Elena replied.\n'
)
