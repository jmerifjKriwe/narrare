"""AuthorVoiceProfile + descriptive renderer (ANAL-007 / ADR-074).

Author voice is structurally the same shape as character voice (deterministic
metrics + LLM qualitative descriptors) but **novel-scoped** — one profile per
novel, persisted as ``ProjectSettings.author_voice`` JSONB per ADR-074. The
contract REUSES the voice-generic types
(:class:`~narrare_core.schemas.voice.VoiceAnalysis` /
:class:`~narrare_core.schemas.voice.VoiceMetrics`) and ADDS author-specific
prose-level metrics (:class:`~narrare_core.analysis.author_metrics.AuthorMetrics`)
plus author-curated examples.

The descriptive/metric boundary (ADR-055/057/074 — binding) is enforced here:
:func:`render_author_voice_for_generation` renders ONLY the descriptive group
into ``{{author_voice}}``. ``voice_analysis.voice_metrics`` and
``author_metrics`` NEVER reach generation — they are comparison-only for the
future Phase 2B author-drift checker.

Module layering (RULE-07): reads ``schemas.voice`` (voice-generic types) and
``analysis.author_metrics`` (AuthorMetrics). Has ZERO imports from ``writing/``
or ``apps/``. Pure renderer — no I/O, no async.

See Also
--------
ADR-074 — Author Voice Storage Contract (the data shape persisted as JSONB).
ADR-055 — Character voice contract (the structural parallel + the boundary
    this module preserves).
ADR-057 — Voice-check checking-path contract (metrics never reach generation).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

# Runtime imports (not TYPE_CHECKING): both AuthorMetrics and VoiceAnalysis
# are used as Pydantic field annotations (``author_metrics: AuthorMetrics | None``,
# ``voice_analysis: VoiceAnalysis | None``). With ``from __future__ import
# annotations`` the annotations are strings at runtime; Pydantic v2 resolves
# them via ``typing.get_type_hints()`` which requires the names to be in scope
# at class-definition time. Mirrors ``profiles/models.py`` (VoiceMetrics as a
# frozen-dataclass field, noqa: TC001).
from narrare_core.analysis.author_metrics import AuthorMetrics  # noqa: TC001
from narrare_core.schemas.voice import VoiceAnalysis  # noqa: TC001


class AuthorVoiceProfile(BaseModel):
    """Machine-derived author-voice profile (ANAL-007 / ADR-074).

    Persisted as ``ProjectSettings.author_voice`` JSONB. Novel-scoped.
    Mirrors the ADR-055 descriptive/metric structure (deterministic metrics +
    LLM qualitative descriptors), REUSING the voice-generic
    :class:`~narrare_core.schemas.voice.VoiceAnalysis` /
    :class:`~narrare_core.schemas.voice.VoiceMetrics` and ADDING
    author-specific prose-level metrics.

    Descriptive group (rendered into ``{{author_voice}}`` by
    :func:`render_author_voice_for_generation`):
        - ``voice_analysis`` descriptive fields (formality, vocabulary_level,
          sentence_profile, emotional_range, cultural_regional_markers,
          voice_examples).
        - ``author_examples``.

    Metric group (comparison ONLY — NEVER rendered into generation):
        - ``voice_analysis.voice_metrics`` (voice-generic metrics).
        - ``author_metrics`` (author-specific prose-level metrics).

    The descriptive/metric boundary is enforced at the consumer contract
    (:func:`render_author_voice_for_generation`), not at the data model — the
    same place ADR-055 enforces it for character voice (``get_speech_data``).
    The profile itself deliberately carries BOTH groups so the future Phase 2B
    author-drift checker can read the metric group via the repository contract.

    Attributes:
        voice_analysis: Voice-generic descriptive block (also carries the
            voice-generic ``voice_metrics`` sub-block).
        author_examples: Author-specific curated representative prose passages
            (the agent's ``author_examples``).
        author_metrics: Author-specific prose-level metrics. Comparison-only.
        updated_at: ISO timestamp of the last profile build (freshness signal).
        is_fresh: Freshness flag (mirrors character-voice ``profiles/_freshness``).
    """

    model_config = ConfigDict(extra="allow")

    voice_analysis: VoiceAnalysis | None = None
    author_examples: list[str] | None = None
    author_metrics: AuthorMetrics | None = None
    updated_at: str | None = None
    is_fresh: bool = True


# ---------------------------------------------------------------------------
# Descriptive-only renderer (binding-boundary enforcement lives here)
# ---------------------------------------------------------------------------


def _formality_descriptor(formality: float) -> str:
    """Map a 0.0-1.0 formality score to a prompt-friendly register word.

    Mirrors :func:`narrare_core.profiles._voice_extraction._formality_descriptor`
    (ADR-055). The numeric value itself is NEVER rendered into generation —
    only this descriptor (the descriptive/metric boundary, ADR-074 binding).
    """
    if formality < 0.34:
        return "casual"
    if formality < 0.67:
        return "balanced"
    return "formal"


def _add_str_field(label: str, value: str | None, parts: list[str]) -> None:
    """Append a labelled string field if non-empty."""
    if value and value.strip():
        parts.append(f"{label}: {value}")


def _add_list_field(label: str, items: list[str] | None, parts: list[str]) -> None:
    """Append a labelled list field if non-empty."""
    if items:
        non_empty = [i for i in items if i and i.strip()]
        if non_empty:
            joined = "; ".join(non_empty)
            parts.append(f"{label}: {joined}")


def _add_voice_analysis_descriptive(voice_analysis: VoiceAnalysis, parts: list[str]) -> None:
    """Render the voice_analysis DESCRIPTIVE group ONLY.

    ADR-074 binding: ``voice_analysis.voice_metrics`` is NEVER read here — the
    metric block is comparison-only (descriptive/metric boundary). Only the
    descriptive fields render into ``{{author_voice}}``.
    """
    # Formality: number → register descriptor (the number is metric-adjacent
    # and must not be rendered as a raw float). bool is a subclass of int, so
    # exclude it explicitly (mirrors _voice_extraction).
    formality = voice_analysis.formality
    if not isinstance(formality, bool) and isinstance(formality, (int, float)):
        parts.append(f"voice: {_formality_descriptor(float(formality))}")

    _add_str_field("vocabulary level", voice_analysis.vocabulary_level, parts)
    _add_str_field("sentence profile", voice_analysis.sentence_profile, parts)
    _add_str_field("emotional range", voice_analysis.emotional_range, parts)
    _add_str_field("markers", voice_analysis.cultural_regional_markers, parts)
    _add_list_field("voice examples", voice_analysis.voice_examples, parts)

    # INTENTIONAL OMISSION: voice_analysis.voice_metrics. Per ADR-074 binding,
    # the metric block is NEVER rendered into {{author_voice}}.


def render_author_voice_for_generation(profile: AuthorVoiceProfile | None) -> str:
    """Render the author-voice DESCRIPTIVE group → ``{{author_voice}}`` text.

    ADR-074 binding (the author-voice analogue of ADR-055 ``get_speech_data``):
    renders ONLY the descriptive group — ``voice_analysis`` descriptive fields
    + ``author_examples``. **MUST NOT** read ``voice_analysis.voice_metrics``
    or ``author_metrics`` (the metric groups are comparison-only for the
    future Phase 2B author-drift checker; they never reach generation).

    RULE-11 graceful degradation: empty / ``None`` profile → empty string
    (generation renders nothing; never a crash or silent prompt regression).

    Args:
        profile: The author-voice profile (``AuthorVoiceProfile`` or ``None``).

    Returns:
        Semicolon-joined descriptive parts, or empty string when no profile /
        no descriptive data.
    """
    if profile is None:
        return ""

    parts: list[str] = []

    if profile.voice_analysis is not None:
        _add_voice_analysis_descriptive(profile.voice_analysis, parts)

    _add_list_field("author examples", profile.author_examples, parts)

    # INTENTIONAL OMISSION: profile.author_metrics. Per ADR-074 binding, the
    # metric block is NEVER rendered into {{author_voice}}.

    return "; ".join(parts) if parts else ""
