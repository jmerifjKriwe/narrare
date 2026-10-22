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

from narrare._app.dependencies_services import StaticModelResolution
from narrare_core.agents.character_voice_types import (
    CharacterVoiceEntry,
    CharacterVoiceOutput,
)
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from pydantic_ai.usage import UsageLimits

    from narrare._app.dependencies_services import ModelResolution
    from narrare.analysis.character_voice_service import CharacterVoiceService
    from narrare.analysis.schemas_character_voice import CharacterVoiceStreamEvent
    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare_core.llm.intents import LLMIntent

# ---------------------------------------------------------------------------
# Fakes (avoid bare MagicMock for domain contracts — RULE-TEST-01)
# ---------------------------------------------------------------------------


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


class _CountingResolution:
    """Fake ModelResolution — counts resolve() calls, never caches.

    Exposes the service-level lazy seam (ADR-086): the service must call
    ``resolve()`` exactly once (first use), never at construction.
    """

    def __init__(self, model: ResolvedModel | None = None) -> None:
        self._model = model if model is not None else _resolved_model()
        self.calls = 0

    async def resolve(self) -> ResolvedModel:
        self.calls += 1
        return self._model


def _resolved_model(config: ResolvedModelConfig | None = None) -> ResolvedModel:
    """A fixed model triple, as the routing cascade would return it."""
    return ResolvedModel(
        config=config or ResolvedModelConfig(provider_name="test", model_id="test-model"),
        source="unit-test",
    )


def make_service(
    composer: FakeComposer,
    config: ResolvedModelConfig,
    *,
    kb_repo: KBRepositoryProtocol | MagicMock | None = None,
    relationship_repo: RelationshipRepository | None = None,
    model_resolution: ModelResolution | None = None,
) -> CharacterVoiceService:
    """Build a CharacterVoiceService wired for Mode 1 prompt resolution.

    Args:
        composer: Fake PromptComposer for DI wiring.
        config: Resolved model config (wrapped in a
            ``StaticModelResolution`` — ADR-086 unit-test harness).
        kb_repo: Optional KB repository for voice-analysis persistence.
        relationship_repo: Optional relationship repository for
            ``kb_relationships`` population. When ``None`` (default), the
            service exercises the graceful degradation path
            (``kb_relationships=""``).
        model_resolution: Optional resolution override (e.g.
            ``_CountingResolution`` for lazy-semantics tests); defaults to
            the static resolution around ``config``.
    """
    from narrare.analysis.character_voice_service import CharacterVoiceService

    novel_repo = AsyncMock()
    chapter_repo = AsyncMock()
    if kb_repo is None:
        kb_repo = AsyncMock()
    if isinstance(kb_repo, AsyncMock):
        # N11 roster gate: the service reads the KB character roster via
        # ``list_entries`` before metrics. Default the mock KB to an empty
        # roster (gate no-op) so attributions pass through exactly as the
        # pre-N11 tests pin them; tests needing a roster set their own.
        kb_repo.list_entries = AsyncMock(return_value=([], 0))
    return CharacterVoiceService(
        novel_repo=novel_repo,  # type: ignore[arg-type]
        chapter_repo=chapter_repo,  # type: ignore[arg-type]
        kb_repo=kb_repo,  # type: ignore[arg-type]
        relationship_repo=relationship_repo,  # type: ignore[arg-type]
        model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
        model_resolution=model_resolution or StaticModelResolution(_resolved_model(config)),
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
