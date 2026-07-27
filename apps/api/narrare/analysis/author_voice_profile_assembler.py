"""AuthorVoiceProfile assembly helper (RULE-04 split).

Extracted from ``author_voice_service.py`` for RULE-04 compliance
(service < 300 lines). Owns the single responsibility of assembling the
persisted :class:`AuthorVoiceProfile` from the pipeline outputs:

- ``voice_analysis`` descriptive fields ← :class:`AuthorVoiceOutput` (agent)
- ``voice_analysis.voice_metrics`` ← :class:`VoiceMetrics` (VoiceMetricsAnalyzer)
- ``author_metrics`` ← :class:`AuthorMetrics` (AuthorMetricsAnalyzer)
- ``author_examples`` ← :class:`AuthorVoiceOutput` (agent)
- ``updated_at`` + ``is_fresh`` ← now / True

The descriptive/metric boundary (ADR-055/057/074) is structural here: the
profile carries BOTH groups (so Phase 2B drift can read the metrics via the
repository), and the GENERATION consumer renders descriptive-only via the
Core :func:`render_author_voice_for_generation`.

See:
    ADR-074 — Author Voice Storage Contract (profile shape + boundary).
    RULE-04 — Modularise, never compress.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from narrare_core.profiles.author_voice import AuthorVoiceProfile
from narrare_core.schemas.voice import VoiceAnalysis

if TYPE_CHECKING:
    # Type-only imports: the assembler is a plain function (not a Pydantic
    # model), so ``from __future__ import annotations`` makes these lazy
    # strings — they are never resolved at runtime. VoiceAnalysis +
    # AuthorVoiceProfile stay at runtime (constructed in the function body).
    from narrare_core.agents.author_voice_types import AuthorVoiceOutput
    from narrare_core.analysis.author_metrics import AuthorMetrics
    from narrare_core.schemas.voice import VoiceMetrics


def assemble_author_voice_profile(
    *,
    descriptive: AuthorVoiceOutput,
    voice_metrics: VoiceMetrics,
    author_metrics: AuthorMetrics,
) -> AuthorVoiceProfile:
    """Assemble the persisted :class:`AuthorVoiceProfile` from the pipeline.

    Mirrors the spec Pipeline step "assemble AuthorVoiceProfile":
        - ``voice_analysis`` descriptive fields ← agent output
        - ``voice_analysis.voice_metrics`` ← VoiceMetricsAnalyzer
        - ``author_metrics`` ← AuthorMetricsAnalyzer
        - ``author_examples`` ← agent output
        - ``updated_at`` + ``is_fresh`` ← now / True

    The descriptive/metric boundary (ADR-055/057/074) is structural: the
    profile carries BOTH groups so Phase 2B drift can read the metrics via
    the repository; the GENERATION consumer renders descriptive-only.

    Args:
        descriptive: The :class:`AuthorVoiceOutput` (descriptive-only —
            binding boundary enforced at the output type).
        voice_metrics: The voice-generic :class:`VoiceMetrics` block.
        author_metrics: The author-specific :class:`AuthorMetrics` block.

    Returns:
        The assembled :class:`AuthorVoiceProfile`, ready to persist.
    """
    voice_analysis = VoiceAnalysis(
        formality=descriptive.formality,
        vocabulary_level=descriptive.vocabulary_level,
        sentence_profile=descriptive.sentence_profile,
        emotional_range=descriptive.emotional_range,
        cultural_regional_markers=descriptive.cultural_regional_markers,
        voice_examples=descriptive.author_examples,
        voice_metrics=voice_metrics,
    )

    return AuthorVoiceProfile(
        voice_analysis=voice_analysis,
        author_examples=descriptive.author_examples,
        author_metrics=author_metrics,
        updated_at=datetime.now(UTC).isoformat(),
        is_fresh=True,
    )
