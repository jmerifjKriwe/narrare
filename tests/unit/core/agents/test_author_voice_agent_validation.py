"""AuthorVoiceAgent — output-type contract + binding-boundary + output-function
+ validator tests.

Split from ``test_author_voice_agent.py`` per RULE-04 (file-size limit — files
ending in ``_agent.py`` have a 200-line cap). This file (which does NOT match
that suffix) gets the default 400-line cap and consolidates the four
output-related test groups:

    - The :class:`AuthorVoiceOutput` descriptive-only contract (formality
      bounds, vocabulary / sentence / emotional-range literal enums).
    - The binding-boundary regression: the output type carries NO metric
      fields (ADR-074 binding — agent produces descriptive only; measurement
      is deterministic).
    - The ``_process_output`` output function (CoreferenceAgent test pattern —
      TestModel's random default output trips the strict validator, so the
      output function is exercised directly).
    - ADR-035 output validation (marker + examples cleanup via ``_validate_output``).

See:
    - ADR-074 (Author Voice Storage Contract — binding boundary invariant).
    - ADR-035 (Agent output validation).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.author_voice_agent import AuthorVoiceAgent
from narrare_core.agents.author_voice_types import (
    AuthorVoiceDeps,
    AuthorVoiceOutput,
)

# ---------------------------------------------------------------------------
# Shared fixtures (mirror test_character_voice_agent.py)
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent() -> AuthorVoiceAgent:
    return AuthorVoiceAgent(model=TestModel())


def _make_ctx(deps: AuthorVoiceDeps | None = None) -> RunContext[AuthorVoiceDeps]:
    return RunContext[AuthorVoiceDeps](
        deps=deps or AuthorVoiceDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


# ---------------------------------------------------------------------------
# Output type contract
# ---------------------------------------------------------------------------


class TestAuthorVoiceOutputContract:
    """AuthorVoiceOutput is descriptive-only (binding boundary: no metric fields)."""

    def test_default_construction(self) -> None:
        out = AuthorVoiceOutput()
        assert out.formality == pytest.approx(0.5)
        assert out.vocabulary_level == "moderate"
        assert out.sentence_profile == "medium"
        assert out.emotional_range == "moderate"
        assert out.cultural_regional_markers is None
        assert out.author_examples == []

    def test_formality_bounded_0_to_1(self) -> None:
        """Pydantic Field enforces the 0.0-1.0 bounds (ADR-035)."""
        AuthorVoiceOutput(formality=0.0)
        AuthorVoiceOutput(formality=1.0)
        with pytest.raises(ValidationError):
            AuthorVoiceOutput(formality=-0.01)
        with pytest.raises(ValidationError):
            AuthorVoiceOutput(formality=1.01)

    def test_vocabulary_level_is_literal_enum(self) -> None:
        AuthorVoiceOutput(vocabulary_level="complex")
        AuthorVoiceOutput(vocabulary_level="simple")
        # model_validate(dict) bypasses pyright's Literal narrowing on kwargs;
        # the runtime test asserts Pydantic rejects the invalid literal.
        with pytest.raises(ValidationError):
            AuthorVoiceOutput.model_validate({"vocabulary_level": "arcane"})

    def test_sentence_profile_is_literal_enum(self) -> None:
        AuthorVoiceOutput(sentence_profile="varied")
        with pytest.raises(ValidationError):
            AuthorVoiceOutput.model_validate({"sentence_profile": "flowery"})

    def test_emotional_range_is_literal_enum(self) -> None:
        AuthorVoiceOutput(emotional_range="expressive")
        with pytest.raises(ValidationError):
            AuthorVoiceOutput.model_validate({"emotional_range": "explosive"})


class TestAuthorVoiceOutputBindingBoundary:
    """REGRESSION: the output type carries NO metric fields (ADR-074 binding).

    The agent's output is descriptive-only. The metric groups
    (``voice_metrics`` / ``author_metrics``) are computed by the deterministic
    analyzers, never produced by the agent. If a future change adds a metric
    field to AuthorVoiceOutput, this test catches it as a boundary regression.
    """

    @pytest.mark.parametrize(
        "forbidden_field",
        [
            "voice_metrics",
            "author_metrics",
            "avg_sentence_length",
            "type_token_ratio",
            "contraction_rate",
            "verbal_tic_frequency",
            "punctuation_profile",
            "dialogue_ratio",
            "description_density",
            "action_introspection_ratio",
            "metaphor_density",
        ],
    )
    def test_metric_field_absent_from_output(self, forbidden_field: str) -> None:
        assert forbidden_field not in AuthorVoiceOutput.model_fields, (
            f"AuthorVoiceOutput must NOT carry metric field '{forbidden_field}' "
            f"(ADR-074 binding — agent output is descriptive-only; measurement is "
            f"deterministic, done by VoiceMetricsAnalyzer / AuthorMetricsAnalyzer)."
        )

    def test_descriptive_field_set_present(self) -> None:
        """The descriptive group fields ARE present (the agent produces them)."""
        expected = {
            "formality",
            "vocabulary_level",
            "sentence_profile",
            "emotional_range",
            "cultural_regional_markers",
            "author_examples",
        }
        assert expected <= set(AuthorVoiceOutput.model_fields.keys())


# ---------------------------------------------------------------------------
# Output function (_process_output) — CoreferenceAgent / CharacterVoiceAgent
# test pattern: TestModel's random default output trips the strict validator,
# so the output function is exercised directly with hand-crafted args.
# ---------------------------------------------------------------------------


class TestProcessOutput:
    """The _process_output output function structures the LLM response."""

    @pytest.mark.asyncio
    async def test_process_output_returns_author_voice_output(
        self, agent: AuthorVoiceAgent
    ) -> None:
        result = await agent._process_output(  # type: ignore[reportPrivateUsage]
            ctx=_make_ctx(),
            formality=0.72,
            vocabulary_level="complex",
            sentence_profile="varied",
            emotional_range="expressive",
            cultural_regional_markers="British, literate register",
            author_examples=["The wind moved.", "She did not turn."],
        )
        assert isinstance(result, AuthorVoiceOutput)
        assert result.formality == pytest.approx(0.72)
        assert result.vocabulary_level == "complex"
        assert result.sentence_profile == "varied"
        assert result.emotional_range == "expressive"
        assert result.cultural_regional_markers == "British, literate register"
        assert result.author_examples == ["The wind moved.", "She did not turn."]

    @pytest.mark.asyncio
    async def test_process_output_with_defaults(self, agent: AuthorVoiceAgent) -> None:
        """No arguments produce a valid default AuthorVoiceOutput."""
        result = await agent._process_output(_make_ctx())
        assert isinstance(result, AuthorVoiceOutput)
        assert result.author_examples == []
        assert result.cultural_regional_markers is None

    @pytest.mark.asyncio
    async def test_process_output_partial_args(self, agent: AuthorVoiceAgent) -> None:
        """The model may return only some fields; the rest take defaults."""
        result = await agent._process_output(
            _make_ctx(),
            formality=0.3,
            vocabulary_level="simple",
        )
        assert result.formality == pytest.approx(0.3)
        assert result.vocabulary_level == "simple"
        assert result.sentence_profile == "medium"  # default
        assert result.emotional_range == "moderate"  # default


# ---------------------------------------------------------------------------
# ADR-035 — output validation (_validate_output)
# ---------------------------------------------------------------------------


class TestValidateOutput:
    """The strict output validator normalizes / cleans up agent output."""

    @pytest.mark.asyncio
    async def test_strips_empty_author_examples(self, agent: AuthorVoiceAgent) -> None:
        out = AuthorVoiceOutput(author_examples=["Real example.", "", "   ", "Another."])
        result = await agent._validate_output(_make_ctx(), out)  # type: ignore[reportPrivateUsage]
        assert result.author_examples == ["Real example.", "Another."]

    @pytest.mark.asyncio
    async def test_normalizes_empty_cultural_markers_to_none(self, agent: AuthorVoiceAgent) -> None:
        out = AuthorVoiceOutput(cultural_regional_markers="   ")
        result = await agent._validate_output(_make_ctx(), out)  # type: ignore[reportPrivateUsage]
        assert result.cultural_regional_markers is None

    @pytest.mark.asyncio
    async def test_preserves_non_empty_cultural_markers(self, agent: AuthorVoiceAgent) -> None:
        out = AuthorVoiceOutput(cultural_regional_markers="British register")
        result = await agent._validate_output(_make_ctx(), out)  # type: ignore[reportPrivateUsage]
        assert result.cultural_regional_markers == "British register"

    @pytest.mark.asyncio
    async def test_preserves_valid_formality(self, agent: AuthorVoiceAgent) -> None:
        """The validator does not second-guess in-range formality (Field-enforced)."""
        out = AuthorVoiceOutput(formality=0.42)
        result = await agent._validate_output(_make_ctx(), out)  # type: ignore[reportPrivateUsage]
        assert result.formality == pytest.approx(0.42)
