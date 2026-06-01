"""Analysis result types — Pydantic models.

These types are the output of analysis computations in ``core/analysis/``
and are consumed by the API layer for serialization.

See Also
--------
ADR-021 — Deterministic Analysis Strategy.
"""

import enum

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


# ---------------------------------------------------------------------------
# ANAL-003: Readability — Result Types
# ---------------------------------------------------------------------------


class ReadabilityMetrics(BaseModel):
    """Formula-based readability scores (deterministic per ADR-021).

    Computed purely from text statistics (syllables, words, sentences) —
    no LLM calls involved.

    Attributes:
        flesch_reading_ease: Flesch Reading Ease score (0-100).
            Higher values indicate easier readability.
        flesch_kincaid_grade: Flesch-Kincaid Grade Level (0-18).
            Approximate US school grade required for comprehension.
        gunning_fog: Gunning Fog Index (0-20).
            Estimated years of formal education needed.
        avg_sentence_length: Mean words per sentence.
        avg_syllables_per_word: Mean syllables per word.
        complex_word_ratio: Proportion of words with ≥ 3 syllables.
        word_count: Total word count in the analyzed text.
        sentence_count: Total sentence count.
    """

    flesch_reading_ease: float
    flesch_kincaid_grade: float
    gunning_fog: float
    avg_sentence_length: float
    avg_syllables_per_word: float
    complex_word_ratio: float
    word_count: int
    sentence_count: int


class SentenceAnalysis(BaseModel):
    """AI analysis of a single sentence's readability.

    Produced by the ``ReadabilityAgent`` via pydantic-ai.  Identifies
    problematic sentences and provides actionable rewrite suggestions
    that preserve the author's voice.

    Attributes:
        sentence: The original sentence text.
        sentence_index: 0-based position of this sentence in the text.
        issues: List of readability problems detected (e.g. ``"too long"``,
            ``"complex vocabulary"``).
        readability_score: Normalised difficulty (0.0 = hardest,
            1.0 = easiest).
        suggestions: Two to three rewrite alternatives that preserve
            meaning and voice.
    """

    sentence: str
    sentence_index: int
    issues: list[str]
    readability_score: float
    suggestions: list[str]


class ReadabilityResult(BaseModel):
    """Complete readability analysis output for a text.

    Combines deterministic formula-based metrics with AI-powered
    sentence-level analysis and genre context.

    Attributes:
        metrics: Formula-based readability scores (deterministic).
        genre_benchmarks: Reference scores keyed by genre label
            (e.g. ``"young_adult"``, ``"commercial_fiction"``).
        sentence_analyses: Per-sentence AI analysis results.
        overall_assessment: Free-text summary from the AI agent.
    """

    metrics: ReadabilityMetrics
    genre_benchmarks: dict[str, ReadabilityMetrics]
    sentence_analyses: list[SentenceAnalysis]
    overall_assessment: str | None = None


# ---------------------------------------------------------------------------
# ANAL-004: POV Analysis — Result Types
# ---------------------------------------------------------------------------


class POVIssueType(enum.StrEnum):
    """Category of POV violation detected in the text.

    Attributes:
        HEAD_HOP: Mid-scene POV switch without scene break.
        KNOWLEDGE_LEAK: POV character knows something they couldn't have
            learned.
        EMOTIONAL_LEAK: Non-POV character's emotions are described
            as felt (not observed).
        PHYSICAL_IMPOSSIBILITY: POV character perceives something beyond
            their sensory reach.
    """

    HEAD_HOP = "head_hop"
    KNOWLEDGE_LEAK = "knowledge_leak"
    EMOTIONAL_LEAK = "emotional_leak"
    PHYSICAL_IMPOSSIBILITY = "physical_impossibility"


class POVIssue(BaseModel):
    """A single POV violation flagged during analysis.

    Attributes:
        type: Category of POV violation.
        location: Chapter / line reference for the problematic passage.
        text: The excerpt containing the violation.
        explanation: Human-readable description of what is wrong.
        suggestion: Concrete suggestion for how to fix the issue.
        severity: ``"error"`` (definite violation) or ``"warning"``
            (potential issue requiring human review).
    """

    type: POVIssueType
    location: str
    text: str
    explanation: str
    suggestion: str
    severity: str  # "error" | "warning"


class POVScene(BaseModel):
    """A single scene with its detected POV character.

    Attributes:
        scene_index: 0-based index of the scene within the chapter.
        start_position: Character offset where this scene begins.
        end_position: Character offset where this scene ends.
        pov_character: Name of the detected POV character, or ``None``
            if the scene appears omniscient / unclear.
        confidence: Confidence score for the POV assignment (0.0-1.0).
    """

    scene_index: int
    start_position: int
    end_position: int
    pov_character: str | None = None
    confidence: float = 0.0


class POVResult(BaseModel):
    """Complete POV analysis output.

    Attributes:
        scenes: Per-scene POV character assignments.
        issues: Flagged POV violations across the text.
        pov_distribution: Fraction of the text attributed to each
            character, as a mapping of character name → proportion
            (0.0-1.0).
        switch_count: Total number of POV switches detected.
        analysis_type: The POV type that was analysed
            (e.g. ``"single_character"``, ``"omniscient"``,
            ``"first_person"``).
    """

    scenes: list[POVScene]
    issues: list[POVIssue]
    pov_distribution: dict[str, float]
    switch_count: int
    analysis_type: str


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
