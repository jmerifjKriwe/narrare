"""Shared fakes + fixtures for SeriesVoiceService unit tests (ADR-030).

Mirrors ``_author_voice_test_helpers.py`` (the novel-level parallel) and
``_band_summary_test_helpers.py`` (the same-module precedent). Domain
behaviour is faked with real classes, not ``MagicMock``:

- The series/novel/chapter repositories use the shared ``tests.fakes.*``
  in-memory fakes.
- The LLM seam (``AuthorVoiceAgent``) is patched via
  :func:`patch_author_voice_pipeline`, exactly like the novel-level
  ``patch_mode1`` — the service reuses the same agent + Mode-1 prompt path.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from narrare_core.agents.author_voice_types import AuthorVoiceOutput
from narrare_core.llm import ResolvedModelConfig
from narrare_core.prompts.composer import ComposedPrompt
from tests.fakes.fake_chapter_repo import FakeChapterRepository
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository

if TYPE_CHECKING:
    from collections.abc import Iterator

    from narrare.series.series_voice_service import SeriesVoiceService


class _FakeComposer:
    """Minimal PromptComposer fake (DI wiring only — compose is patched)."""

    def __init__(self) -> None:
        self.build = AsyncMock(
            return_value=ComposedPrompt(system="COMPOSED-AUTHOR-VOICE-SYSTEM", user="")
        )


class _FakeModelRegistry:
    """Fake ModelRegistry returning a stub Model."""

    def __init__(self) -> None:
        self.get_model = AsyncMock(return_value=MagicMock(spec=object))


class _FakeComposedInvocation:
    """Stand-in for ``ComposedInvocation`` (Mode 1)."""

    def __init__(self, system: str = "COMPOSED-AUTHOR-VOICE-SYSTEM", user: str = "") -> None:
        self.composed_prompt = ComposedPrompt(system=system, user=user)


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


def make_config() -> ResolvedModelConfig:
    """A default ``ResolvedModelConfig`` for SeriesVoiceService tests."""
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


def make_service(
    *,
    series_repo: FakeSeriesRepository | None = None,
    novel_repo: FakeNovelRepository | None = None,
    chapter_repo: FakeChapterRepository | None = None,
) -> tuple[SeriesVoiceService, FakeSeriesRepository, FakeNovelRepository, FakeChapterRepository]:
    """Build a SeriesVoiceService wired with fakes (agent patched per-test).

    Returns ``(service, series_repo, novel_repo, chapter_repo)`` so tests can
    seed data and assert interactions.
    """
    from narrare.series.series_voice_service import SeriesVoiceService

    series_repo = series_repo or FakeSeriesRepository()
    novel_repo = novel_repo or FakeNovelRepository()
    chapter_repo = chapter_repo or FakeChapterRepository()

    service = SeriesVoiceService(
        series_repo=series_repo,  # type: ignore[arg-type]
        novel_repo=novel_repo,  # type: ignore[arg-type]
        chapter_repo=chapter_repo,  # type: ignore[arg-type]
        model_registry=_FakeModelRegistry(),  # type: ignore[arg-type]
        model_config=make_config(),
        composer=_FakeComposer(),  # type: ignore[arg-type]
    )
    return service, series_repo, novel_repo, chapter_repo


@contextmanager
def patch_author_voice_pipeline(
    output: AuthorVoiceOutput | None = None,
) -> Iterator[MagicMock]:
    """Patch AuthorVoiceAgent, AuthorVoiceDeps, and compose_invocation (Mode 1).

    The patched ``AuthorVoiceAgent`` returns ``output`` from ``.run()``.
    Yields the ``MockAgent`` constructor so tests can assert instantiation.
    Mirrors ``_author_voice_test_helpers.patch_mode1``.
    """
    agent_output = output or make_agent_output()
    with (
        patch("narrare_core.agents.author_voice_agent.AuthorVoiceAgent") as MockAgent,
        patch("narrare_core.agents.author_voice_agent.AuthorVoiceDeps"),
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(return_value=_FakeComposedInvocation()),
        ),
    ):
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=agent_output)
        MockAgent.return_value = mock_agent
        yield MockAgent


#: Real narrator prose (3+ chapters) so the deterministic metric analyzers
#: produce non-None VoiceMetrics / AuthorMetrics (mirrors the author-voice
#: sample prose). Above the MIN_CHAPTERS_FOR_SERIES_PROFILE threshold.
SAMPLE_PROSE = (
    "The wind moved through the long grass like a rumour, carrying the "
    'scent of distant rain. She paused at the threshold. "You came," she said.'
)
