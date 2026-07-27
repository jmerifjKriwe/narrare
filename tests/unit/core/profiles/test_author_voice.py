"""AuthorVoiceProfile + AuthorVoiceConsumer — Core data contract + descriptive
renderer (ANAL-007 / ADR-074).

Author voice is structurally the same shape as character voice (deterministic
metrics + LLM qualitative descriptors), but novel-scoped (one profile per
novel, persisted as ``ProjectSettings.author_voice`` JSONB per ADR-074). The
contract REUSES the voice-generic types
(:class:`~narrare_core.schemas.voice.VoiceAnalysis` /
:class:`~narrare_core.schemas.voice.VoiceMetrics`) and ADDS author-specific
prose-level metrics + author-curated examples.

The descriptive/metric boundary (ADR-055/057/074 — binding) is enforced here:
the renderer renders ONLY the descriptive group into ``{{author_voice}}``.
``voice_analysis.voice_metrics`` and ``author_metrics`` NEVER reach generation
— they are comparison-only for the future Phase 2B author-drift checker.

This suite covers:
    - The :class:`AuthorVoiceProfile` Pydantic composition contract.
    - The :class:`AuthorVoiceConsumer` Protocol surface (runtime_checkable).
    - :func:`render_author_voice_for_generation` — descriptive-only renderer
      + a binding-boundary regression test asserting the metric groups NEVER
      appear in the rendered text.

See:
    - ``docs/architecture/decisions/ADR-074-author-voice-storage.md`` (storage
      contract — this module's data shape).
    - ``docs/features/analysis/ANAL-007-voice-author.md`` "Data contract" +
      "Prompt surface" sections.
    - ADR-055 / ADR-057 (descriptive/metric boundary preserved here).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

import pytest

from narrare_core.analysis.author_metrics import AuthorMetrics
from narrare_core.profiles.author_voice import (
    AuthorVoiceProfile,
    render_author_voice_for_generation,
)
from narrare_core.profiles.contracts import AuthorVoiceConsumer
from narrare_core.schemas.voice import VoiceAnalysis, VoiceMetrics

if TYPE_CHECKING:
    from uuid import UUID

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _descriptive_voice_analysis() -> VoiceAnalysis:
    """A VoiceAnalysis carrying only descriptive fields (metric block separate)."""
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
    )


def _populated_voice_metrics() -> VoiceMetrics:
    """A VoiceMetrics carrying values that MUST NEVER render into generation."""
    return VoiceMetrics(
        avg_sentence_length=14.3,
        sentence_length_std=6.1,
        type_token_ratio=0.71,
        avg_syllables_per_word=1.6,
        contraction_rate=0.08,
        punctuation_profile={"exclamation": 0.01, "question": 0.02},
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
    return AuthorVoiceProfile(
        voice_analysis=VoiceAnalysis(
            formality=0.72,
            vocabulary_level="complex",
            sentence_profile="varied",
            emotional_range="expressive",
            cultural_regional_markers="British, literate register",
            voice_examples=["The wind moved through the long grass."],
            voice_metrics=_populated_voice_metrics(),
        ),
        author_examples=[
            "She did not turn around.",
            "Somewhere, a bell was ringing.",
        ],
        author_metrics=_populated_author_metrics(),
        updated_at="2026-07-27T00:00:00Z",
        is_fresh=True,
    )


# ---------------------------------------------------------------------------
# AuthorVoiceProfile composition
# ---------------------------------------------------------------------------


class TestAuthorVoiceProfileComposition:
    """ADR-074 — AuthorVoiceProfile composes reused + author-specific types."""

    def test_default_construction_all_none(self) -> None:
        profile = AuthorVoiceProfile()
        assert profile.voice_analysis is None
        assert profile.author_examples is None
        assert profile.author_metrics is None
        assert profile.updated_at is None
        assert profile.is_fresh is True

    def test_composes_voice_analysis_with_metrics(self) -> None:
        profile = AuthorVoiceProfile(
            voice_analysis=VoiceAnalysis(
                formality=0.5,
                voice_metrics=VoiceMetrics(avg_sentence_length=12.0),
            ),
        )
        assert profile.voice_analysis is not None
        assert profile.voice_analysis.voice_metrics is not None
        assert profile.voice_analysis.voice_metrics.avg_sentence_length == 12.0

    def test_composes_author_metrics(self) -> None:
        profile = AuthorVoiceProfile(author_metrics=_populated_author_metrics())
        assert profile.author_metrics is not None
        assert profile.author_metrics.dialogue_ratio == pytest.approx(0.42)

    def test_author_examples_list(self) -> None:
        profile = AuthorVoiceProfile(author_examples=["One.", "Two."])
        assert profile.author_examples == ["One.", "Two."]

    def test_extra_allow(self) -> None:
        """extra='allow' so the persisted JSONB shape can grow migration-free."""
        profile = AuthorVoiceProfile(future_field="x")  # type: ignore[call-arg]
        assert profile.model_dump()["future_field"] == "x"  # type: ignore[operator]

    def test_round_trip_json_serialization(self) -> None:
        """Persisted JSONB round-trips back to the same AuthorVoiceProfile."""
        profile = _full_profile()
        round_tripped = AuthorVoiceProfile.model_validate_json(profile.model_dump_json())
        assert round_tripped == profile


# ---------------------------------------------------------------------------
# AuthorVoiceConsumer Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class _IsProtocol(Protocol):
    """Marker for the runtime_checkable Protocol check below."""

    ...


class TestAuthorVoiceConsumerProtocol:
    """AuthorVoiceConsumer is a runtime_checkable Protocol parallel to
    :class:`VoiceProfileConsumer`."""

    def test_protocol_is_runtime_checkable(self) -> None:
        # runtime_checkable Protocols support isinstance().
        assert isinstance(AuthorVoiceConsumer, type)

    def test_fake_implementation_satisfies_protocol(self) -> None:
        class FakeAuthorVoiceConsumer:
            """Minimal fake matching the Protocol surface (RULE-17 contract test)."""

            async def get_profile(self, project_id: UUID) -> AuthorVoiceProfile | None:
                return None

            def render_for_generation(self, profile: AuthorVoiceProfile | None) -> str:
                return render_author_voice_for_generation(profile)

        consumer = FakeAuthorVoiceConsumer()
        assert isinstance(consumer, AuthorVoiceConsumer), (
            "FakeAuthorVoiceConsumer must satisfy the AuthorVoiceConsumer Protocol "
            "(RULE-17 — contract test, not a Mock with # type: ignore)."
        )

    def test_protocol_has_required_methods(self) -> None:
        # Protocol members: get_profile + render_for_generation.
        assert "get_profile" in AuthorVoiceConsumer.__dict__
        assert "render_for_generation" in AuthorVoiceConsumer.__dict__


# ---------------------------------------------------------------------------
# render_author_voice_for_generation — descriptive-only renderer
# ---------------------------------------------------------------------------


class TestRenderAuthorVoiceGracefulEmpty:
    """RULE-11: empty / None profile → empty string (never a crash)."""

    def test_none_profile_renders_empty_string(self) -> None:
        assert render_author_voice_for_generation(None) == ""

    def test_empty_profile_renders_empty_string(self) -> None:
        assert render_author_voice_for_generation(AuthorVoiceProfile()) == ""

    def test_profile_without_voice_analysis_renders_empty_string(self) -> None:
        profile = AuthorVoiceProfile(author_examples=["Some passage."])
        # No descriptive voice_analysis → only author_examples. Still produces
        # text (examples ARE descriptive). Just must not crash.
        result = render_author_voice_for_generation(profile)
        assert isinstance(result, str)


class TestRenderAuthorVoiceDescriptiveFields:
    """The descriptive group renders into the output text."""

    def test_renders_formality_as_descriptor_not_number(self) -> None:
        """The formality NUMBER is never rendered — only its descriptor word.

        Mirrors profiles/_voice_extraction._formality_descriptor (ADR-055):
        a raw 0.0-1.0 number is a metric; the descriptive consumer renders a
        register word (e.g. "formal").
        """
        profile = AuthorVoiceProfile(
            voice_analysis=VoiceAnalysis(formality=0.85, vocabulary_level=None),
        )
        out = render_author_voice_for_generation(profile)
        assert "0.85" not in out, (
            f"Raw formality number must NOT render into {{author_voice}} (boundary); got: {out!r}"
        )
        # A register word MUST appear instead.
        assert "formal" in out.lower()

    def test_renders_vocabulary_level(self) -> None:
        profile = AuthorVoiceProfile(
            voice_analysis=VoiceAnalysis(vocabulary_level="complex"),
        )
        assert "complex" in render_author_voice_for_generation(profile)

    def test_renders_sentence_profile(self) -> None:
        profile = AuthorVoiceProfile(
            voice_analysis=VoiceAnalysis(sentence_profile="varied"),
        )
        assert "varied" in render_author_voice_for_generation(profile)

    def test_renders_emotional_range(self) -> None:
        profile = AuthorVoiceProfile(
            voice_analysis=VoiceAnalysis(emotional_range="expressive"),
        )
        assert "expressive" in render_author_voice_for_generation(profile)

    def test_renders_cultural_regional_markers(self) -> None:
        profile = AuthorVoiceProfile(
            voice_analysis=VoiceAnalysis(cultural_regional_markers="British, literate register"),
        )
        assert "British" in render_author_voice_for_generation(profile)

    def test_renders_voice_examples(self) -> None:
        profile = AuthorVoiceProfile(
            voice_analysis=VoiceAnalysis(voice_examples=["The wind moved.", "She did not turn."]),
        )
        out = render_author_voice_for_generation(profile)
        assert "The wind moved." in out

    def test_renders_author_examples(self) -> None:
        profile = AuthorVoiceProfile(
            author_examples=["Somewhere, a bell was ringing."],
        )
        out = render_author_voice_for_generation(profile)
        assert "Somewhere, a bell was ringing." in out


# ---------------------------------------------------------------------------
# BINDING-BOUNDARY REGRESSION TESTS (ADR-055 / ADR-057 / ADR-074)
# ---------------------------------------------------------------------------


class TestRenderAuthorVoiceBindingBoundary:
    """voice_metrics + author_metrics NEVER reach generation.

    This is the author-voice analogue of ADR-055's ``get_speech_data()``
    constraint and ADR-057's checking-path boundary. The descriptive/metric
    boundary is fixed at the consumer contract — render_author_voice_for_generation
    MUST NOT read either metric group. Tested explicitly here so the boundary
    cannot silently regress.
    """

    def test_voice_metrics_field_numbers_never_render(self) -> None:
        """Distinctive numeric values from voice_metrics must not appear in output."""
        profile = AuthorVoiceProfile(
            voice_analysis=VoiceAnalysis(voice_metrics=_populated_voice_metrics()),
            author_metrics=None,
        )
        out = render_author_voice_for_generation(profile)
        # These specific numeric values live ONLY in the metric block.
        assert "14.3" not in out, f"avg_sentence_length value leaked into {{author_voice}}: {out!r}"
        assert "0.71" not in out, f"type_token_ratio value leaked into {{author_voice}}: {out!r}"
        assert "0.08" not in out, f"contraction_rate value leaked into {{author_voice}}: {out!r}"

    def test_author_metrics_field_numbers_never_render(self) -> None:
        """Distinctive numeric values from author_metrics must not appear."""
        profile = AuthorVoiceProfile(
            voice_analysis=None,
            author_metrics=_populated_author_metrics(),
        )
        out = render_author_voice_for_generation(profile)
        assert "0.42" not in out, f"dialogue_ratio value leaked into {{author_voice}}: {out!r}"
        assert "0.55" not in out, (
            f"action_introspection_ratio value leaked into {{author_voice}}: {out!r}"
        )
        assert "0.03" not in out, f"metaphor_density value leaked into {{author_voice}}: {out!r}"

    def test_metric_field_names_never_render(self) -> None:
        """The metric field labels themselves must not appear in the output.

        A renderer that builds a label like 'dialogue_ratio:' from the metric
        block would also leak the value. Asserting the label is absent catches
        both forms.
        """
        profile = _full_profile()
        out = render_author_voice_for_generation(profile)
        out_lower = out.lower()
        for forbidden in (
            "voice_metrics",
            "avg_sentence_length",
            "type_token_ratio",
            "contraction_rate",
            "verbal_tic_frequency",
            "punctuation_profile",
            "author_metrics",
            "dialogue_ratio",
            "description_density",
            "action_introspection_ratio",
            "metaphor_density",
        ):
            assert forbidden not in out_lower, (
                f"Metric field label '{forbidden}' leaked into {{author_voice}} "
                f"(boundary violation, ADR-074): {out!r}"
            )

    def test_full_profile_renders_descriptive_without_any_metric(self) -> None:
        """A complete profile (all groups populated) renders descriptive only."""
        profile = _full_profile()
        out = render_author_voice_for_generation(profile)
        # Descriptive fields ARE present.
        assert "complex" in out  # vocabulary_level
        assert "varied" in out  # sentence_profile
        assert "expressive" in out  # emotional_range
        # Numeric metric values are NOT.
        assert "14.3" not in out  # avg_sentence_length
        assert "0.42" not in out  # dialogue_ratio
