"""Shared test helpers for AuthorVoiceService tests (RULE-04 split).

Provides fakes and fixtures used by ``test_author_voice_service.py``
(happy path + storage contract), ``test_author_voice_service_errors.py``
(RULE-11), and ``test_author_voice_prompt_path_compliance.py`` (Mode 1).

Mirrors the ``_character_voice_test_helpers.py`` pattern (ADR-054 precedent).
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from narrare_core.agents.author_voice_types import AuthorVoiceOutput
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from pydantic_ai.usage import UsageLimits

    from narrare.analysis.author_voice_service import AuthorVoiceService
    from narrare.analysis.schemas_author_voice import AuthorVoiceStreamEvent
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.llm.model_config import ResolvedModelConfig

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
            return_value=ComposedPrompt(system="COMPOSED-AUTHOR-VOICE-SYSTEM", user="")
        )


class FakeComposedInvocation:
    """Stand-in for ``ComposedInvocation`` (Mode 1).

    The service only reads ``invocation.composed_prompt`` (Mode 1
    invariant), so a lightweight class with that attribute is sufficient.
    """

    def __init__(self, system: str = "COMPOSED-AUTHOR-VOICE-SYSTEM", user: str = "") -> None:
        self.composed_prompt: ComposedPrompt = ComposedPrompt(system=system, user=user)


class FakeAuthorVoiceRepository:
    """Fake AuthorVoiceRepository — records load/save/clear calls.

    Implements the same surface as
    :class:`narrare.analysis.author_voice_repository.AuthorVoiceRepository`
    so the service can be wired without a real DB session. Stores at most one
    profile per novel_id (the production repository's storage shape).
    """

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, object] = {}
        self.save_calls: list[tuple[uuid.UUID, object]] = []
        self.clear_calls: list[uuid.UUID] = []
        self.load_calls: list[uuid.UUID] = []

    async def load(self, novel_id: uuid.UUID) -> object | None:
        self.load_calls.append(novel_id)
        return self._store.get(novel_id)

    async def save(self, novel_id: uuid.UUID, profile: object) -> None:
        self.save_calls.append((novel_id, profile))
        self._store[novel_id] = profile

    async def clear(self, novel_id: uuid.UUID) -> None:
        self.clear_calls.append(novel_id)
        self._store.pop(novel_id, None)


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
        "content": overrides.get("content", _SAMPLE_PROSE),
    }
    defaults.update(overrides)
    chapter = MagicMock(spec=Chapter)
    for k, v in defaults.items():
        setattr(chapter, k, v)
    return chapter


def make_agent_output(
    *,
    formality: float = 0.6,
    vocabulary_level: str = "complex",
    sentence_profile: str = "varied",
    emotional_range: str = "expressive",
    cultural_regional_markers: str | None = "literary register",
    author_examples: list[str] | None = None,
) -> AuthorVoiceOutput:
    """Build a fake AuthorVoiceAgent.run result (descriptive-only)."""
    if author_examples is None:
        author_examples = [
            "The wind moved through the long grass like a rumour.",
            "She paused at the threshold, weighing the cost of every word.",
        ]
    return AuthorVoiceOutput(
        formality=formality,
        vocabulary_level=vocabulary_level,  # type: ignore[arg-type]
        sentence_profile=sentence_profile,  # type: ignore[arg-type]
        emotional_range=emotional_range,  # type: ignore[arg-type]
        cultural_regional_markers=cultural_regional_markers,
        author_examples=author_examples,
    )


def make_service(
    composer: FakeComposer,
    config: ResolvedModelConfig,
    *,
    repository: FakeAuthorVoiceRepository | None = None,
) -> AuthorVoiceService:
    """Build an AuthorVoiceService wired for Mode 1 prompt resolution.

    Args:
        composer: Fake PromptComposer for DI wiring.
        config: Resolved model config.
        repository: Optional AuthorVoiceRepository fake. When ``None``
            (default), a fresh :class:`FakeAuthorVoiceRepository` is created
            so each test asserts against its own save/clear call list.
    """
    from narrare.analysis.author_voice_service import AuthorVoiceService

    novel_repo = AsyncMock()
    chapter_repo = AsyncMock()
    return AuthorVoiceService(
        novel_repo=novel_repo,  # type: ignore[arg-type]
        chapter_repo=chapter_repo,  # type: ignore[arg-type]
        repository=repository or FakeAuthorVoiceRepository(),  # type: ignore[arg-type]
        model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
        model_config=config,
        composer=composer,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Shared async-generator + patch utilities (used across the RULE-04 split)
# ---------------------------------------------------------------------------


async def consume(
    stream: AsyncIterator[AuthorVoiceStreamEvent],
) -> list[AuthorVoiceStreamEvent]:
    """Collect all events from the service async generator."""
    return [event async for event in stream]


@contextmanager
def patch_mode1(
    system: str = "COMPOSED-AUTHOR-VOICE-SYSTEM", user: str = ""
) -> Iterator[tuple[MagicMock, MagicMock, AsyncMock]]:
    """Patch AuthorVoiceAgent, AuthorVoiceDeps, and compose_invocation (Mode 1).

    Yields ``(MockAgent, MockDeps, mock_compose)``. The ``MockAgent``
    constructor must be wired to a fake ``run`` by each caller.
    """
    with (
        patch("narrare_core.agents.author_voice_agent.AuthorVoiceAgent") as MockAgent,
        patch("narrare_core.agents.author_voice_agent.AuthorVoiceDeps") as MockDeps,
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(return_value=FakeComposedInvocation(system=system, user=user)),
        ) as mock_compose,
    ):
        yield MockAgent, MockDeps, mock_compose


# ---------------------------------------------------------------------------
# Sample prose (3+ chapters of narrator prose for a meaningful profile)
# ---------------------------------------------------------------------------

#: Three short chapters of narrator prose (narration + a little dialogue
#: together) — enough for VoiceMetricsAnalyzer.analyze_text +
#: AuthorMetricsAnalyzer.analyze to produce non-None metrics, and well above
#: the MIN_CHAPTERS_FOR_PROFILE threshold so the soft-warning path is NOT
#: exercised by default (the warning path is tested explicitly).
_SAMPLE_PROSE = (
    "The wind moved through the long grass like a rumour, carrying the "
    "scent of distant rain. She paused at the threshold, weighing the cost "
    'of every word. "You came," she said quietly.'
)
