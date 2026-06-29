"""Value types for voice analysis (ANAL-008 / ADR-055).

``AttributedUtterance`` is the shared boundary type between the
deterministic :class:`~narrare_core.analysis.dialogue_parser.DialogueParser`
(producer) and the deterministic
:class:`~narrare_core.analysis.voice_metrics.VoiceMetricsAnalyzer`
(consumer). Keeping it in a dedicated, dependency-free module lets both
analyzers import it without an ``analysis`` → ``analysis`` cycle and
keeps each analyzer file focused on one responsibility (RULE-04 / RULE-06).

See Also
--------
ADR-021 — Deterministic analysis strategy.
ADR-055 — Character voice storage contract (Decision 2 hybrid metrics).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AttributedUtterance:
    """A single piece of quoted speech with speaker attribution + confidence.

    Produced by :class:`~narrare_core.analysis.dialogue_parser.DialogueParser`
    and consumed by
    :class:`~narrare_core.analysis.voice_metrics.VoiceMetricsAnalyzer`.

    Attributes:
        text: The dialogue content (text inside the quotation marks).
        speaker: The attributed speaker name, or ``None`` when no
            deterministic attribution could be made (left for the LLM
            ``CharacterVoiceAgent`` to resolve inline per ADR-055 Decision 3).
        confidence: Attribution confidence in ``[0.0, 1.0]``. Tag-attributed
            utterances (``"said Elena"``) score high; action-beat and
            em-dash attributions score medium; untagged quotes score low.
        start: Character offset of the opening quote in the source prose.
        end: Character offset one past the closing quote (exclusive).
    """

    text: str
    speaker: str | None = None
    confidence: float = 0.0
    start: int = 0
    end: int = 0
