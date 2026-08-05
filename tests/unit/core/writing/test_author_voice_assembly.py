"""Author-voice assembly through WritingContextAssembler (ANAL-007 / ADR-074).

Tests the cross-feature wiring: the WritingContextAssembler populates
``WritingContext.author_voice`` from the ``AuthorVoiceConsumer`` (parallel to
``character_voice_profiles`` from the ``VoiceProfileConsumer``).

Boundary regression (ADR-074 binding): the rendered ``{{author_voice}}`` text
MUST contain descriptive fields (formality descriptor, vocabulary_level, … +
author_examples) but NEVER raw ``voice_metrics`` or ``author_metrics`` (the
metric groups are comparison-only for the future Phase 2B author-drift checker).

RULE-11 graceful degradation: no consumer / no project / no profile →
``author_voice = ""`` (generation proceeds without it).

The Series Voice Hierarchy Delta-model assembly (Spec 3 / ADR-078) is tested
in :mod:`tests.unit.core.writing.test_author_voice_delta_assembly` (RULE-04
split — the combined file exceeded the 400-line hard limit).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from narrare_core.analysis.author_metrics import AuthorMetrics
from narrare_core.profiles.author_voice import (
    AuthorVoiceProfile,
    render_author_voice_for_generation,
)
from narrare_core.schemas.voice import VoiceAnalysis, VoiceMetrics
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.models import WritingContext

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.profiles.author_voice_consumer import AuthorVoiceConsumer

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _descriptive_voice_analysis() -> VoiceAnalysis:
    """A VoiceAnalysis carrying descriptive fields + a populated metric block."""
    return VoiceAnalysis(
        formality=0.72,
        vocabulary_level="complex",
        sentence_profile="varied",
        emotional_range="expressive",
        cultural_regional_markers="British, literate register",
        voice_examples=[
            "The wind moved through the long grass.",
            "She did not turn around.",
        ],
        # Metric block — MUST NEVER render into {{author_voice}}.
        voice_metrics=VoiceMetrics(
            avg_sentence_length=14.3,
            sentence_length_std=6.1,
            type_token_ratio=0.71,
            avg_syllables_per_word=1.6,
            contraction_rate=0.08,
            punctuation_profile={"exclamation": 0.01, "question": 0.02},
        ),
    )


def _populated_author_metrics() -> AuthorMetrics:
    """AuthorMetrics carrying values that MUST NEVER render into generation."""
    return AuthorMetrics(
        dialogue_ratio=0.42,
        description_density=0.18,
        action_introspection_ratio=0.55,
        metaphor_density=0.03,
    )


def _full_profile() -> AuthorVoiceProfile:
    """A profile carrying BOTH descriptive + metric groups (the full shape)."""
    return AuthorVoiceProfile(
        voice_analysis=_descriptive_voice_analysis(),
        author_examples=[
            "She did not turn around.",
            "Somewhere, a bell was ringing.",
        ],
        author_metrics=_populated_author_metrics(),
        updated_at="2026-07-27T00:00:00Z",
        is_fresh=True,
    )


class _FakeAuthorVoiceConsumer:
    """Fake AuthorVoiceConsumer for assembler tests.

    Uses the Core ``render_author_voice_for_generation`` renderer (the same
    function the real Backend consumer delegates to) so the boundary is
    exercised identically to production.

    ``resolve_for_generation`` (the Delta-model generation API, Spec 3) is
    satisfied for protocol compliance; the legacy novel-only path is retained
    for the boundary-regression tests here. The Delta-aware variant lives in
    :mod:`tests.unit.core.writing.test_author_voice_delta_assembly`.
    """

    def __init__(self, profile: AuthorVoiceProfile | None) -> None:
        self._profile = profile
        self._project_id: UUID | None = None

    async def get_profile(self, project_id: UUID) -> AuthorVoiceProfile | None:
        self._project_id = project_id
        return self._profile

    def render_for_generation(self, profile: AuthorVoiceProfile | None) -> str:
        return render_author_voice_for_generation(profile)

    async def resolve_for_generation(
        self,
        project_id: UUID,
        series_id: UUID | None = None,
    ) -> str:
        """Legacy-equivalent resolution: novel-only, ignores series context.

        The Delta-aware variant lives in
        :class:`tests.unit.core.writing.test_author_voice_delta_assembly._FakeDeltaAuthorVoiceConsumer`.
        Keeping this one novel-only preserves the boundary-regression tests'
        original intent (a standalone novel's descriptive-only render).
        """
        del project_id, series_id
        return self.render_for_generation(self._profile)


class _NullAuthorVoiceConsumer:
    """Fake consumer that always returns None / empty (no profile stored)."""

    async def get_profile(self, project_id: UUID) -> AuthorVoiceProfile | None:
        del project_id
        return None

    def render_for_generation(self, profile: AuthorVoiceProfile | None) -> str:
        return render_author_voice_for_generation(profile)

    async def resolve_for_generation(
        self,
        project_id: UUID,
        series_id: UUID | None = None,
    ) -> str:
        del project_id, series_id
        return ""


@pytest.fixture()
def assembler() -> WritingContextAssembler:
    """Default assembler with 6000-token budget."""
    return WritingContextAssembler(total_budget=6000)


# ---------------------------------------------------------------------------
# Tests: WritingContextAssembler populates author_voice
# ---------------------------------------------------------------------------


class TestAuthorVoiceAssembly:
    """Author-voice population through assembler.assemble()."""

    @pytest.mark.asyncio
    async def test_author_voice_populated_when_profile_stored(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Profile stored → author_voice populated with descriptive content."""
        consumer: AuthorVoiceConsumer = _FakeAuthorVoiceConsumer(_full_profile())

        ctx = await assembler.assemble(
            project_id=uuid4(),
            chapter_content="The chapter begins.",
            author_voice_consumer=consumer,
            project_title="Test",
            genre="fantasy",
        )

        assert isinstance(ctx, WritingContext)
        assert ctx.author_voice != ""

        # Descriptive fields render into the text.
        assert "formal" in ctx.author_voice  # formality 0.72 → "formal"
        assert "complex" in ctx.author_voice  # vocabulary_level
        assert "varied" in ctx.author_voice  # sentence_profile
        assert "expressive" in ctx.author_voice  # emotional_range
        assert "British" in ctx.author_voice  # cultural_regional_markers
        assert "The wind moved" in ctx.author_voice  # voice_examples
        assert "She did not turn around" in ctx.author_voice  # author_examples

    @pytest.mark.asyncio
    async def test_author_voice_empty_when_no_profile(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """No profile stored → author_voice = "" (RULE-11 graceful)."""
        consumer: AuthorVoiceConsumer = _NullAuthorVoiceConsumer()

        ctx = await assembler.assemble(
            project_id=uuid4(),
            chapter_content="The chapter begins.",
            author_voice_consumer=consumer,
        )

        assert ctx.author_voice == ""

    @pytest.mark.asyncio
    async def test_author_voice_empty_when_no_consumer(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """No consumer injected → author_voice = "" (RULE-11 graceful)."""
        ctx = await assembler.assemble(
            project_id=uuid4(),
            chapter_content="The chapter begins.",
        )

        assert ctx.author_voice == ""

    @pytest.mark.asyncio
    async def test_author_voice_empty_when_no_project_id(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """No project_id → author_voice = "" (consumer not called)."""
        consumer: AuthorVoiceConsumer = _FakeAuthorVoiceConsumer(_full_profile())

        ctx = await assembler.assemble(
            chapter_content="The chapter begins.",
            author_voice_consumer=consumer,
        )

        assert ctx.author_voice == ""

    @pytest.mark.asyncio
    async def test_author_voice_parallel_to_character_voice_profiles(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Both voice field can coexist — author + character (default empty)."""
        consumer: AuthorVoiceConsumer = _FakeAuthorVoiceConsumer(_full_profile())

        ctx = await assembler.assemble(
            project_id=uuid4(),
            chapter_content="The chapter begins.",
            author_voice_consumer=consumer,
        )

        # Author voice is populated from the consumer.
        assert ctx.author_voice != ""
        # Character voice profiles default to "" (no voice_profile_consumer).
        assert ctx.character_voice_profiles == ""


# ---------------------------------------------------------------------------
# Tests: Boundary regression — metrics NEVER reach generation
# ---------------------------------------------------------------------------


class TestAuthorVoiceBoundaryRegression:
    """ADR-074 binding: generation NEVER sees raw metrics.

    The rendered ``{{author_voice}}`` text (via ``to_prompt_variables()``)
    MUST contain descriptive fields but NEVER ``voice_metrics`` or
    ``author_metrics`` values. This is the author-voice analogue of the
    ADR-055 ``get_speech_data`` boundary for character voice.
    """

    @pytest.mark.asyncio
    async def test_rendered_author_voice_contains_no_voice_metrics(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """voice_metrics values MUST NOT appear in author_voice."""
        consumer: AuthorVoiceConsumer = _FakeAuthorVoiceConsumer(_full_profile())

        ctx = await assembler.assemble(
            project_id=uuid4(),
            chapter_content="Content.",
            author_voice_consumer=consumer,
        )

        variables = ctx.to_prompt_variables()
        author_voice_text = variables["author_voice"]

        # Descriptive fields ARE present.
        assert "formal" in author_voice_text
        assert "complex" in author_voice_text

        # voice_metrics values are NOT present.
        assert "14.3" not in author_voice_text  # avg_sentence_length
        assert "6.1" not in author_voice_text  # sentence_length_std
        assert "0.71" not in author_voice_text  # type_token_ratio
        assert "1.6" not in author_voice_text  # avg_syllables_per_word
        assert "0.08" not in author_voice_text  # contraction_rate
        assert "exclamation" not in author_voice_text  # punctuation_profile key

    @pytest.mark.asyncio
    async def test_rendered_author_voice_contains_no_author_metrics(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """author_metrics values MUST NOT appear in author_voice."""
        consumer: AuthorVoiceConsumer = _FakeAuthorVoiceConsumer(_full_profile())

        ctx = await assembler.assemble(
            project_id=uuid4(),
            chapter_content="Content.",
            author_voice_consumer=consumer,
        )

        author_voice_text = ctx.to_prompt_variables()["author_voice"]

        # author_metrics values are NOT present.
        assert "0.42" not in author_voice_text  # dialogue_ratio
        assert "0.18" not in author_voice_text  # description_density
        assert "0.55" not in author_voice_text  # action_introspection_ratio
        assert "0.03" not in author_voice_text  # metaphor_density

    @pytest.mark.asyncio
    async def test_author_voice_in_prompt_variables(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """to_prompt_variables() includes author_voice key (template rendering)."""
        consumer: AuthorVoiceConsumer = _FakeAuthorVoiceConsumer(_full_profile())

        ctx = await assembler.assemble(
            project_id=uuid4(),
            chapter_content="Content.",
            author_voice_consumer=consumer,
        )

        variables = ctx.to_prompt_variables()
        assert "author_voice" in variables
        assert variables["author_voice"] == ctx.author_voice

    @pytest.mark.asyncio
    async def test_author_voice_empty_renders_empty_in_variables(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """No profile → author_voice = "" in to_prompt_variables() (no crash)."""
        ctx = await assembler.assemble(
            project_id=uuid4(),
            chapter_content="Content.",
        )

        variables = ctx.to_prompt_variables()
        assert variables["author_voice"] == ""
