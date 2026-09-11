"""Shared test helpers for WRITE-010 voice-check service tests."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch

from narrare.analysis.voice_check_service import CharacterVoiceCheckerService
from narrare_core.agents.character_voice_checker_types import (
    CharacterVoiceCheckerEntry,
    CharacterVoiceCheckerOutput,
    FlaggedLine,
)
from narrare_core.kb.schemas.character import VoiceMetrics
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.profiles.models import CharacterVoiceProfile
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from pydantic_ai.usage import UsageLimits

    from narrare.analysis.schemas_voice_check import VoiceCheckStreamEvent
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.intents import LLMIntent
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
    """Fake ModelRegistry returning a stub Model.

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
    """Fake PromptComposer for Mode-1 DI wiring."""

    def __init__(self) -> None:
        self.build: AsyncMock = AsyncMock(
            return_value=ComposedPrompt(system="COMPOSED-VOICE-CHECK-SYSTEM", user="")
        )


class FakeComposedInvocation:
    """Stand-in for a Mode-1 composed invocation."""

    def __init__(self, system: str = "COMPOSED-VOICE-CHECK-SYSTEM", user: str = "") -> None:
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
    """Chapter repository fake with call tracking."""

    def __init__(self, chapter: FakeChapter | None) -> None:
        self.chapter = chapter
        self.calls: list[tuple[str, uuid.UUID]] = []

    async def get(self, chapter_id: uuid.UUID) -> FakeChapter | None:
        self.calls.append(("get", chapter_id))
        return self.chapter


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
        raise AssertionError("voice check must not use the generation projection")

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
    stream: AsyncIterator[VoiceCheckStreamEvent],
) -> list[VoiceCheckStreamEvent]:
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
        content=str(overrides.get("content", SAMPLE_DIALOGUE)),
    )


def make_profile(name: str = "Elena") -> CharacterVoiceProfile:
    """Build a stored voice profile with deterministic metrics."""
    return CharacterVoiceProfile(
        character_id=str(uuid.uuid4()),
        name=name,
        speech_summary="formal register, measured sentences, precise vocabulary",
        voice_metrics=VoiceMetrics(
            avg_sentence_length=5.0,
            sentence_length_std=1.0,
            type_token_ratio=0.8,
            avg_syllables_per_word=1.4,
            contraction_rate=0.0,
            punctuation_profile={"comma": 0.2},
        ),
    )


def make_agent_output() -> CharacterVoiceCheckerOutput:
    """Build a fake CharacterVoiceCheckerAgent output for two characters."""
    return CharacterVoiceCheckerOutput(
        characters=[
            CharacterVoiceCheckerEntry(
                character_name="Elena",
                match_judgment="mostly_consistent",
                qualitative_sub_score=80.0,
                flagged_lines=[
                    FlaggedLine(
                        quote="Sure it is.",
                        reason="Too casual for Elena's established formal register.",
                    )
                ],
            ),
            CharacterVoiceCheckerEntry(
                character_name="Marc",
                match_judgment="consistent",
                qualitative_sub_score=95.0,
                flagged_lines=[],
            ),
        ]
    )


def make_service(
    *,
    novel: FakeNovel | None,
    chapter: FakeChapter | None,
    consumer: FakeVoiceProfileConsumer,
    config: ResolvedModelConfig,
    composer: FakeComposer | None = None,
    relationship_repo: RelationshipRepository | None = None,
) -> CharacterVoiceCheckerService:
    """Build a CharacterVoiceCheckerService with fakes and casts at the boundary."""
    novel_repo = FakeNovelRepository(novel)
    chapter_repo = FakeChapterRepository(chapter)

    async def consumer_provider(project_id: uuid.UUID) -> VoiceProfileConsumer:
        consumer.calls.append(("provider", project_id))
        return cast("VoiceProfileConsumer", consumer)

    # Casts are confined to the test composition boundary: fakes implement the
    # methods exercised by the service Protocols but do not subclass concrete repos.
    return CharacterVoiceCheckerService(
        novel_repo=cast("NovelRepository", novel_repo),
        chapter_repo=cast("ChapterRepository", chapter_repo),
        model_registry=cast("ModelRegistry", FakeModelRegistry()),
        consumer_provider=consumer_provider,
        model_config=config,
        composer=cast("PromptComposer", composer or FakeComposer()),
        relationship_repo=relationship_repo,  # type: ignore[arg-type]
    )


@contextmanager
def patch_mode1(
    system: str = "COMPOSED-VOICE-CHECK-SYSTEM", user: str = ""
) -> Iterator[tuple[MagicMock, AsyncMock]]:
    """Patch the checker agent and Mode-1 composition function."""
    with (
        patch("narrare.analysis.voice_check_agent_runner.CharacterVoiceCheckerAgent") as MockAgent,
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(return_value=FakeComposedInvocation(system=system, user=user)),
        ) as mock_compose,
    ):
        yield MockAgent, mock_compose


SAMPLE_DIALOGUE = (
    '"One must consider the consequences," said Elena.\n'
    '"Yeah. Nope," Marc replied.\n'
    '"This is not a trivial matter," Elena said.\n'
    '"Sure it is," Marc replied.\n'
)
