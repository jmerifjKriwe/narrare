"""AuthorMetricsAnalyzer — deterministic prose-level metrics (ANAL-007 / ADR-074).

The author-voice-specific half of ADR-021's hybrid measurement strategy. Where
:class:`~narrare_core.analysis.voice_metrics.VoiceMetricsAnalyzer` measures
voice-generic signals (sentence length, TTR, contractions, …) over per-speaker
dialogue OR full prose, this analyzer computes the **author-specific**
prose-level metrics that have no character-voice analogue:

    - ``dialogue_ratio``             — quoted-dialogue word count / total words.
    - ``description_density``        — modifier (adj/adv) density proxy.
    - ``action_introspection_ratio`` — introspection-marker density vs action density.
    - ``metaphor_density``           — simile / figurative-cue density (PROVISIONAL).

The model is **pure** — no I/O, no state, no LLM — and **deterministic** (ADR-021):
identical input always yields identical output. Quote-span extraction delegates
to :func:`narrare_core.nlp.dialogue.extract_dialogue` (RULE-07/08:
``analysis → nlp``; pure regex, no raw spaCy outside ``core/nlp/``).

Every field is ``float | None`` in ``[0.0, 1.0]`` so the
:func:`~narrare_core.analysis.voice_check_scoring.voice_metric_distances` delta
primitive (ADR-057/073) generalises to author metrics in ANAL-009 Phase 2B
drift.

The descriptive/metric boundary (ADR-055/057/074) is preserved:
:class:`AuthorMetrics` NEVER reach generation. They are comparison-only for
the future Phase 2B author-drift checker.

Provisionality (ADR-074 + spec metaphor_density decision): the metric set is
eval-tunable via ADR-032. ``extra="allow"`` on :class:`AuthorMetrics` lets the
set grow without a migration, and any field can be dropped to ``None``
migration-free if ADR-032 evals show a proxy is too noisy for drift.

The curated lexicons + suffix + pattern sets live in
:mod:`narrare_core.analysis._author_metrics_lexicons` (RULE-04 split — they
are eval-tunable data, reviewed independently from the analyzer logic).

See Also
--------
ADR-021 — Deterministic analysis strategy.
ADR-074 — Author Voice Storage Contract (AuthorMetrics shape).
ADR-055 / ADR-057 — Descriptive/metric boundary this module preserves.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

from narrare_core.analysis._author_metrics_lexicons import (
    ACTION_CUES,
    ADJECTIVE_SUFFIXES,
    ADVERB_SUFFIXES,
    FIGURATIVE_LEXICON,
    INTROSPECTION_CUES,
    SIMILE_CUE_PATTERNS,
)
from narrare_core.nlp.dialogue import extract_dialogue

# ---------------------------------------------------------------------------
# Tokenisation pattern (mirror VoiceMetricsAnalyzer's approach for determinism)
# ---------------------------------------------------------------------------

#: Word tokens — alphabetic + apostrophes + accented chars. Same character class
#: as VoiceMetricsAnalyzer._WORD_RE so dialogue_ratio's word counts are
#: directly comparable across the two analyzers.
_WORD_RE: re.Pattern[str] = re.compile(r"[a-zA-Z'\u00C0-\u024F]+")


class AuthorMetrics(BaseModel):
    """Author-specific PROSE-LEVEL metrics — comparison ONLY (ANAL-009 Phase 2B).

    NEVER rendered into generation. Populated by the deterministic
    :class:`AuthorMetricsAnalyzer`, never by the LLM agent. ``extra="allow"``
    lets the metric block grow without a migration (ADR-074 binding).

    Every field is ``float | None`` in ``[0.0, 1.0]`` so the
    :func:`~narrare_core.analysis.voice_check_scoring.voice_metric_distances`
    delta primitive generalises trivially to author metrics in Phase 2B.

    Attributes:
        dialogue_ratio: Quoted-dialogue word count / total word count
            (``0.0``-``1.0``). Deterministic, stable.
        description_density: Modifier (adj/adv) density proxy
            (``0.0`` sparse - ``1.0`` rich). Deterministic; provisional.
        action_introspection_ratio: Introspection-marker density vs action
            density (``0.0`` action-heavy -> ``1.0`` introspection-heavy).
            Deterministic; provisional.
        metaphor_density: Simile/figurative-cue density (``0.0``-``1.0``).
            Deterministic; deliberately crude; the hardest metric - see the
            spec's metaphor_density decision (Q1).
    """

    model_config = ConfigDict(extra="allow")

    dialogue_ratio: float | None = None
    description_density: float | None = None
    action_introspection_ratio: float | None = None
    metaphor_density: float | None = None


class AuthorMetricsAnalyzer:
    """Deterministic prose-level author-voice metrics (ANAL-007 / ADR-074).

    All methods are pure — no state, no I/O, no LLM. ``analyze`` never raises
    on empty or malformed prose (RULE-11): such cases produce sensible
    defaults (``None`` fields).

    Configurability (RULE-18): the suffix + lexicon sets are exposed as
    overridable class-level constants (sourced from
    :mod:`narrare_core.analysis._author_metrics_lexicons`), mirroring
    :class:`~narrare_core.analysis.dialogue_parser.DialogueParser.DEFAULT_CONTEXT_WINDOW`
    and :class:`~narrare_core.analysis.voice_metrics.VoiceMetricsAnalyzer` defaults.
    They are eval-tunable (ADR-032 / ADR-074 provisional-metric policy).
    """

    #: Adjective suffixes used by the description_density proxy. RULE-18 pattern.
    DEFAULT_ADJECTIVE_SUFFIXES: tuple[str, ...] = ADJECTIVE_SUFFIXES

    #: Adverb suffixes used by the description_density proxy. RULE-18 pattern.
    DEFAULT_ADVERB_SUFFIXES: tuple[str, ...] = ADVERB_SUFFIXES

    #: Introspection-cue lexicon for action_introspection_ratio. RULE-18 pattern.
    DEFAULT_INTROSPECTION_CUES: tuple[str, ...] = INTROSPECTION_CUES

    #: Action-cue lexicon for action_introspection_ratio. RULE-18 pattern.
    DEFAULT_ACTION_CUES: tuple[str, ...] = ACTION_CUES

    #: Simile-cue regex patterns for metaphor_density. RULE-18 pattern.
    DEFAULT_SIMILE_CUE_PATTERNS: tuple[re.Pattern[str], ...] = SIMILE_CUE_PATTERNS

    #: Figurative-cue lexicon for metaphor_density. RULE-18 pattern.
    DEFAULT_FIGURATIVE_LEXICON: tuple[str, ...] = FIGURATIVE_LEXICON

    def __init__(
        self,
        *,
        adjective_suffixes: tuple[str, ...] = DEFAULT_ADJECTIVE_SUFFIXES,
        adverb_suffixes: tuple[str, ...] = DEFAULT_ADVERB_SUFFIXES,
        introspection_cues: tuple[str, ...] = DEFAULT_INTROSPECTION_CUES,
        action_cues: tuple[str, ...] = DEFAULT_ACTION_CUES,
        simile_cue_patterns: tuple[re.Pattern[str], ...] = DEFAULT_SIMILE_CUE_PATTERNS,
        figurative_lexicon: tuple[str, ...] = DEFAULT_FIGURATIVE_LEXICON,
    ) -> None:
        self._adjective_suffixes = adjective_suffixes
        self._adverb_suffixes = adverb_suffixes
        self._modifier_suffixes = adjective_suffixes + adverb_suffixes
        self._introspection_cues = frozenset(introspection_cues)
        self._action_cues = frozenset(action_cues)
        self._simile_cue_patterns = simile_cue_patterns
        self._figurative_lexicon = frozenset(figurative_lexicon)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, chapter_prose: list[str]) -> AuthorMetrics:
        """Compute prose-level author metrics over the supplied chapter texts.

        Args:
            chapter_prose: Full chapter prose (one string per chapter;
                narration + dialogue together). 3+ chapters recommended for a
                meaningful profile (the caller enforces the threshold).

        Returns:
            A populated :class:`AuthorMetrics`. RULE-11: empty / all-blank
            input → all-None (graceful degradation, never raises).
        """
        non_empty = [t for t in chapter_prose if t and t.strip()]
        if not non_empty:
            return AuthorMetrics()

        # Word-tokenise each chapter the same way VoiceMetricsAnalyzer does so
        # the four ratios are directly comparable to the voice-generic metrics.
        all_words: list[str] = []
        for text in non_empty:
            all_words.extend(self._extract_words(text))
        if not all_words:
            return AuthorMetrics()

        total_words = len(all_words)

        return AuthorMetrics(
            dialogue_ratio=self._dialogue_ratio(non_empty, total_words),
            description_density=self._description_density(all_words, total_words),
            action_introspection_ratio=self._action_introspection_ratio(all_words),
            metaphor_density=self._metaphor_density(non_empty, total_words),
        )

    # ------------------------------------------------------------------
    # Tokenisation
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_words(text: str) -> list[str]:
        """Lowercase word tokens, apostrophes preserved for contraction parity."""
        return [w.lower() for w in _WORD_RE.findall(text)]

    # ------------------------------------------------------------------
    # Metric: dialogue_ratio
    # ------------------------------------------------------------------

    @staticmethod
    def _dialogue_ratio(non_empty_texts: list[str], total_words: int) -> float:
        """Quoted-dialogue word count / total word count (DialogueParser spans).

        Uses :func:`extract_dialogue` from ``core/nlp/dialogue`` (RULE-07/08) —
        the same pure-regex quote-span extractor :class:`DialogueParser` builds
        on. Deterministic. Bounded ``[0.0, 1.0]`` by construction.
        """
        if total_words == 0:
            return 0.0
        dialogue_word_count = 0
        for text in non_empty_texts:
            for line in extract_dialogue(text):
                dialogue_word_count += len(AuthorMetricsAnalyzer._extract_words(line.text))
        return dialogue_word_count / total_words

    # ------------------------------------------------------------------
    # Metric: description_density (adj/adv suffix proxy)
    # ------------------------------------------------------------------

    def _description_density(self, words: list[str], total_words: int) -> float:
        """Modifier-density proxy — (adj + adv suffix token count) / total tokens.

        Deterministic suffix-based heuristic. Provisional per ADR-074 / spec.
        Bounded ``[0.0, 1.0]``.
        """
        if total_words == 0:
            return 0.0
        modifier_count = sum(1 for w in words if self._is_modifier(w))
        return modifier_count / total_words

    def _is_modifier(self, word: str) -> bool:
        """True if *word* (lowercase) ends with an adjective/adverb suffix.

        Crude by design — provisional per spec. Accepts false positives
        ("decision" / "lion") and false negatives; tunable via ADR-032.
        """
        # Minimum length 4 to avoid matching tiny stems like "ly" / "icy".
        if len(word) < 4:
            return False
        return any(word.endswith(suffix) for suffix in self._modifier_suffixes)

    # ------------------------------------------------------------------
    # Metric: action_introspection_ratio
    # ------------------------------------------------------------------

    def _action_introspection_ratio(self, words: list[str]) -> float:
        """Introspection-marker count / (introspection + action) marker count.

        ``0.0`` = action-heavy, ``1.0`` = introspection-heavy. Returns ``0.0``
        when neither set occurs (no signal → action-neutral default).
        Bounded ``[0.0, 1.0]`` by construction.
        """
        introspection_count = sum(1 for w in words if w in self._introspection_cues)
        action_count = sum(1 for w in words if w in self._action_cues)
        denominator = introspection_count + action_count
        if denominator == 0:
            return 0.0
        return introspection_count / denominator

    # ------------------------------------------------------------------
    # Metric: metaphor_density (simile/figurative-cue proxy — CRUDEST)
    # ------------------------------------------------------------------

    def _metaphor_density(self, non_empty_texts: list[str], total_words: int) -> float:
        """Simile-cue density + figurative-lexicon density (PROVISIONAL).

        Per the spec's metaphor_density decision (Q1, option B): deterministic
        simile-cue proxy. Counts occurrences of simile patterns ("like a",
        "as a", "as if", "as though") plus a small curated figurative lexicon,
        normalized by word count. Crude but deterministic + stable — exactly
        what a drift-comparable metric must be. Bounded ``[0.0, 1.0]``.
        """
        if total_words == 0:
            return 0.0
        combined = "\n".join(non_empty_texts)
        cue_count = 0
        for pattern in self._simile_cue_patterns:
            cue_count += len(pattern.findall(combined))
        for word in self._extract_words(combined):
            if word in self._figurative_lexicon:
                cue_count += 1
        return cue_count / total_words
