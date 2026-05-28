"""Analysis result types — Pydantic models.

These types are the output of analysis computations in ``core/analysis/``
and are consumed by the API layer for serialization.

See Also
--------
ADR-021 — Deterministic Analysis Strategy.
"""

from pydantic import BaseModel


class VADScores(BaseModel):
    """Valence-Arousal-Dominance scores for a text unit.

    Attributes:
        valence: Pleasantness ( -1 = unpleasant, +1 = pleasant).
        arousal: Intensity ( -1 = calm, +1 = excited).
        dominance: Control ( -1 = submissive, +1 = dominant).
    """

    valence: float
    arousal: float
    dominance: float


class EmotionScores(BaseModel):
    """Emotion category scores for a text unit.

    Each emotion has a float score (0.0 to 1.0) representing the
    proportion of words in this text unit that evoke that emotion.
    """

    anger: float = 0.0
    anticipation: float = 0.0
    disgust: float = 0.0
    fear: float = 0.0
    joy: float = 0.0
    sadness: float = 0.0
    surprise: float = 0.0
    trust: float = 0.0
    positive: float = 0.0
    negative: float = 0.0


class SentenceSentiment(BaseModel):
    """Sentiment analysis for a single sentence.

    Attributes:
        sentence: The sentence text.
        sentence_index: 0-based index in the text's sentence list.
        vad: Valence-Arousal-Dominance scores.
        emotions: Emotion category scores.
        word_count: Number of tokens in this sentence.
        is_dialogue: Whether this sentence contains dialogue.
        dominant_emotion: The emotion category with the highest score.
    """

    sentence: str
    sentence_index: int
    vad: VADScores
    emotions: EmotionScores
    word_count: int
    is_dialogue: bool = False
    dominant_emotion: str | None = None


class NarrativeArc(BaseModel):
    """Detected narrative arc from sentiment progression.

    Attributes:
        arc_type: The detected narrative arc type.
        confidence: How well the text matches this arc (0.0 to 1.0).
        segments: List of arc segments (e.g. ``"exposition"``,
            ``"rising_action"``, ``"climax"``, ``"falling_action"``,
            ``"resolution"``) with VAD per segment.
        explanation: Human-readable description of why this arc was detected.
    """

    arc_type: str = "unknown"
    confidence: float = 0.0
    # TODO(ANAL-002): Replace with a typed segment model once arc detection
    # is implemented.  Current dict shape: {name, valence, arousal, dominance}.
    segments: list[dict[str, object]] = []
    explanation: str = ""


class SentimentOverview(BaseModel):
    """Aggregate sentiment analysis for an entire text (chapter).

    Attributes:
        sentence_count: Number of sentences analyzed.
        average_vad: Mean VAD scores across all sentences.
        overall_emotions: Aggregate emotion scores across all sentences.
        narrative_arc: Detected narrative arc (if enough sentences).
        sentences: Per-sentence sentiment breakdown.
        dominant_emotions: Top emotion categories across the text.
        warnings: Data-quality warnings (e.g. low word count, arc limits).
    """

    sentence_count: int
    average_vad: VADScores
    overall_emotions: EmotionScores
    narrative_arc: NarrativeArc | None = None
    sentences: list[SentenceSentiment] = []
    dominant_emotions: list[str] = []
    warnings: list[str] = []
