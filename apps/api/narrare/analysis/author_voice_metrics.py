"""Author-voice deterministic metrics computation (ANAL-007 / ADR-074).

Single responsibility: compute the two deterministic metric groups for the
ADR-074 hybrid pipeline over a novel's selected chapters — voice-generic
metrics (:class:`VoiceMetricsAnalyzer.analyze_text` over the narrator's FULL
prose, narration + dialogue together) and author-specific prose-level metrics
(:class:`AuthorMetricsAnalyzer.analyze`).

Extracted from ``author_voice_service.py`` for RULE-04 compliance (the
service crossed the 300-line limit when it gained the ADR-086
``ensure_resolved`` lifecycle; plan §2.7 split convention —
``author_voice_drift_pipeline.py`` precedent for module-level analyzer
factories).

The agent INTERPRETS these metrics; it never recomputes them (ADR-074
binding boundary). Measurement is deterministic (ADR-021).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.analysis.author_metrics import AuthorMetricsAnalyzer
from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer

if TYPE_CHECKING:
    from narrare_core.analysis.author_metrics import AuthorMetrics
    from narrare_core.analysis.voice_metrics import VoiceMetrics


def _make_voice_metrics_analyzer(language: str) -> VoiceMetricsAnalyzer:
    return VoiceMetricsAnalyzer(language=language)


def _make_author_metrics_analyzer() -> AuthorMetricsAnalyzer:
    return AuthorMetricsAnalyzer()


def compute_author_voice_metrics(
    chapter_prose: list[str],
    language: str,
) -> tuple[VoiceMetrics, AuthorMetrics]:
    """Compute voice-generic + author-specific metrics over the full prose.

    Args:
        chapter_prose: The selected chapters' full text (narration + dialogue
            together — the author-voice measurement vocabulary is
            voice-generic, ADR-074 type-reuse).
        language: Writing language code (drives voice-metric tokenisation).

    Returns:
        ``(voice_metrics, author_metrics)`` — consumed by the profile
        assembler AND rendered as model-interpreted summaries (the agent
        never recomputes them — ADR-074 binding).
    """
    voice_metrics = _make_voice_metrics_analyzer(language).analyze_text(chapter_prose)
    author_metrics = _make_author_metrics_analyzer().analyze(chapter_prose)
    return voice_metrics, author_metrics
