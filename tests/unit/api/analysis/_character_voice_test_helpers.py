"""Shared test helpers for CharacterVoiceService tests (RULE-04 split).

Provides fakes and fixtures used by ``test_character_voice_service.py``
(happy path + write contract), ``test_character_voice_service_errors.py``
(RULE-11), and ``test_character_voice_prompt_path_compliance.py`` (Mode 1).

Mirrors the ``_coreference_test_helpers.py`` pattern (ADR-054 precedent).
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from narrare_core.agents.character_voice_types import (
    CharacterVoiceEntry,
    CharacterVoiceOutput,
)
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from narrare.analysis.character_voice_service import CharacterVoiceService
    from narrare.analysis.schemas_character_voice import CharacterVoiceStreamEvent
    from narrare_core.llm.model_config import ResolvedModelConfig

# ---------------------------------------------------------------------------
# Fakes (avoid bare MagicMock for domain contracts — RULE-TEST-01)
# ---------------------------------------------------------------------------


class FakeModelRegistry:
    """Fake ModelRegistry returning a stub Model."""

    def __init__(self) -> None:
        self.get_model: AsyncMock = AsyncMock(return_value=MagicMock(spec=object))


class FakeComposer:
    """Fake PromptComposer for DI wiring.

    The service routes through ``compose_invocation`` (which calls
    ``composer.build`` internally), so this fake only needs to exist for DI
    wiring — its ``build`` is never reached when ``compose_invocation`` is
    patched. Kept as a real object (not a bare MagicMock) so the service's
    ``composer is None`` guard is satisfied.
    """

    def __init__(self) -> None:
        self.build: AsyncMock = AsyncMock(
            return_value=ComposedPrompt(system="COMPOSED-CHARACTER-VOICE-SYSTEM", user="")
        )


class FakeComposedInvocation:
    """Stand-in for ``ComposedInvocation`` (Mode 1).

    The service only reads ``invocation.composed_prompt`` (Mode 1
    invariant), so a lightweight class with that attribute is sufficient.
    """

    def __init__(self, system: str = "COMPOSED-CHARACTER-VOICE-SYSTEM", user: str = "") -> None:
        self.composed_prompt: ComposedPrompt = ComposedPrompt(system=system, user=user)


# ---------------------------------------------------------------------------
# Domain object builders
# ---------------------------------------------------------------------------


def make_novel(**overrides: object) -> MagicMock:
    """Create a mock novel with the attributes the service reads."""
    from narrare.novels.models import Novel

    defaults: dict[str, object] = {
        "id": overrides.get("id", uuid.uuid4()),
        "title": overrides.get("title", "Test Novel"),
        "genre": overrides.get("genre", "Fantasy"),
        "writing_language": overrides.get("writing_language", "en"),
    }
    defaults.update(overrides)
    novel = MagicMock(spec=Novel)
    for k, v in defaults.items():
        setattr(novel, k, v)
    return novel


def make_chapter(**overrides: object) -> MagicMock:
    """Create a mock chapter with the attributes the service reads."""
    from narrare.chapters.models import Chapter

    novel_id = overrides.get("novel_id", uuid.uuid4())
    defaults: dict[str, object] = {
        "id": overrides.get("id", uuid.uuid4()),
        "novel_id": novel_id,
        "title": overrides.get("title", "Chapter 1"),
        "content": overrides.get("content", _SAMPLE_DIALOGUE),
    }
    defaults.update(overrides)
    chapter = MagicMock(spec=Chapter)
    for k, v in defaults.items():
        setattr(chapter, k, v)
    return chapter


def make_kb_entry(
    *,
    name: str = "Elena",
    entity_type: str = "character",
    metadata: dict[str, object] | None = None,
) -> MagicMock:
    """Create a mock KBEntry with the attributes the service reads/writes."""
    from datetime import UTC, datetime

    from narrare.kb.models import KBEntry

    entry = MagicMock(spec=KBEntry)
    entry.id = uuid.uuid4()
    entry.name = name
    entry.entity_type = entity_type
    entry.metadata_ = dict(metadata) if metadata is not None else {}
    entry.updated_at = datetime.now(UTC)
    return entry


def make_agent_output(
    *,
    characters: list[CharacterVoiceEntry] | None = None,
) -> CharacterVoiceOutput:
    """Build a fake CharacterVoiceAgent.run result."""
    if characters is None:
        characters = [
            CharacterVoiceEntry(
                character_name="Elena",
                formality=0.7,
                vocabulary_level="complex",
                sentence_profile="long",
                emotional_range="expressive",
                cultural_regional_markers="formal court register",
                voice_examples=["One must consider the consequences."],
                distinctiveness_notes="More formal than Marc.",
            ),
            CharacterVoiceEntry(
                character_name="Marc",
                formality=0.2,
                vocabulary_level="simple",
                sentence_profile="short",
                emotional_range="restricted",
                cultural_regional_markers=None,
                voice_examples=["Yeah. Nope."],
                distinctiveness_notes="Blunter than Elena.",
            ),
        ]
    return CharacterVoiceOutput(characters=characters)


def make_service(
    composer: FakeComposer,
    config: ResolvedModelConfig,
    *,
    kb_repo: MagicMock | None = None,
) -> CharacterVoiceService:
    """Build a CharacterVoiceService wired for Mode 1 prompt resolution."""
    from narrare.analysis.character_voice_service import CharacterVoiceService

    novel_repo = AsyncMock()
    chapter_repo = AsyncMock()
    return CharacterVoiceService(
        novel_repo=novel_repo,  # type: ignore[arg-type]
        chapter_repo=chapter_repo,  # type: ignore[arg-type]
        kb_repo=kb_repo or AsyncMock(),  # type: ignore[arg-type]
        model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
        model_config=config,
        composer=composer,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Shared async-generator + patch utilities (used across the RULE-04 split)
# ---------------------------------------------------------------------------


async def consume(
    stream: AsyncIterator[CharacterVoiceStreamEvent],
) -> list[CharacterVoiceStreamEvent]:
    """Collect all events from the service async generator."""
    return [event async for event in stream]


@contextmanager
def patch_mode1(
    system: str = "COMPOSED-CHARACTER-VOICE-SYSTEM", user: str = ""
) -> Iterator[tuple[MagicMock, MagicMock, AsyncMock]]:
    """Patch CharacterVoiceAgent, CharacterVoiceDeps, and compose_invocation (Mode 1).

    Yields ``(MockAgent, MockDeps, mock_compose)``. The ``MockAgent``
    constructor must be wired to a fake ``run`` by each caller.
    """
    with (
        patch("narrare_core.agents.character_voice_agent.CharacterVoiceAgent") as MockAgent,
        patch("narrare_core.agents.character_voice_agent.CharacterVoiceDeps") as MockDeps,
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(return_value=FakeComposedInvocation(system=system, user=user)),
        ) as mock_compose,
    ):
        yield MockAgent, MockDeps, mock_compose


# ---------------------------------------------------------------------------
# Sample dialogue (deterministically attributable by DialogueParser)
# ---------------------------------------------------------------------------

#: Two speakers with clear speech-verb tags so DialogueParser attributes both
#: deterministically (high confidence) — giving VoiceMetricsAnalyzer two
#: per-character metric groups to feed the agent.
_SAMPLE_DIALOGUE = (
    '"One must consider the consequences," said Elena.\n'
    "She paused, weighing her words.\n"
    '"Yeah. Nope," Marc replied.\n'
    "He shrugged and turned away.\n"
    '"This is not a trivial matter," Elena said.\n'
    '"Sure it is," Marc replied.\n'
)
