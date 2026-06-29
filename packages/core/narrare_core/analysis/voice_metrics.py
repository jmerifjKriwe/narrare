"""VoiceMetricsAnalyzer — deterministic per-character voice metrics (ANAL-008/ADR-021).

Computes per-utterance hard metrics (sentence-length distribution, type-token
ratio, avg syllables/word, contraction rate, verbal-tic n-gram frequency,
punctuation habits) and aggregates them per character. The result feeds
ANAL-009 drift comparison and WRITE-010 checking, which need stable,
comparable numbers (ADR-021).

The model is **pure** — no I/O, no state, no LLM — and **deterministic**:
identical input always yields identical output (ADR-021). Syllable counting
delegates to :func:`narrare_core.nlp.syllables.count_syllables` (RULE-07/08:
``analysis → nlp``, no raw spaCy outside ``core/nlp/``).

Layering (ADR-055 Decision 2): this analyzer owns the *measurement* half of
character voice profiling. The qualitative half (formality, emotional range,
cultural markers, distinctiveness) is the :class:`CharacterVoiceAgent`'s job
(Core-2c) — never this analyzer's.

See Also
--------
ADR-021 — Deterministic analysis strategy.
ADR-055 — Character voice storage contract (Decision 2 hybrid metrics).
"""

from __future__ import annotations

import re
from statistics import mean, pstdev
from typing import TYPE_CHECKING

from narrare_core.kb.schemas.character import VoiceMetrics
from narrare_core.nlp.syllables import count_syllables

if TYPE_CHECKING:
    from narrare_core.analysis.voice_types import AttributedUtterance
    from narrare_core.nlp.contracts_types import LanguageCode

# ---------------------------------------------------------------------------
# Tokenisation patterns (shared with FormulaReadabilityAnalyzer's approach)
# ---------------------------------------------------------------------------

#: Word tokens — alphabetic + apostrophes + accented chars. Apostrophes are
#: kept so contraction detection (``don't``, ``she's``) works on whole tokens.
_WORD_RE: re.Pattern[str] = re.compile(r"[a-zA-Z'\u00C0-\u024F]+")

#: Sentence boundary — punctuation followed by whitespace. Handles ``.``,
#: ``!``, ``?``, and the ellipsis character ``\u2026``.
_SENTENCE_SPLIT_RE: re.Pattern[str] = re.compile(r"(?<=[.!?…])\s+")

#: Ellipsis — three consecutive dots ``...`` or the Unicode ellipsis ``\u2026``.
_ELLIPSIS_RE: re.Pattern[str] = re.compile(r"\.\.\.|\u2026")

#: Em dash character (U+2014).
_EM_DASH: str = "\u2014"

#: Punctuation habit keys tracked in the profile (≤5 — RULE-18 safe at
#: module level). Each maps to a counting strategy in :meth:`_punctuation_profile`.
_PUNCTUATION_HABITS: tuple[str, ...] = ("exclamation", "question", "ellipsis", "em_dash")


class VoiceMetricsAnalyzer:
    """Deterministic per-character voice metrics from attributed utterances.

    Consumes :class:`AttributedUtterance` objects (produced by
    :class:`~narrare_core.analysis.dialogue_parser.DialogueParser`), groups
    them by speaker, and computes a :class:`VoiceMetrics` block per character.

    All methods are pure — no state, no I/O. ``analyze`` never raises on
    empty text, missing data, or a single utterance (RULE-11): such cases
    produce sensible defaults (``None`` fields or zero rates).

    Args:
        contraction_suffixes: Apostrophe suffixes that unambiguously mark a
            token as a contraction (``n't``, ``'re``, ``'ve``, …). Defaults
            to :attr:`DEFAULT_CONTRACTION_SUFFIXES`. Configurable per RULE-18
            (class-level annotated default + constructor injection, matching
            :class:`DialogueParser.DEFAULT_CONTEXT_WINDOW`).
        contraction_s_bases: Words that form valid ``'s`` contractions
            (pronouns + common words). A noun + ``'s`` (possessive) is NOT
            a contraction. Defaults to :attr:`DEFAULT_CONTRACTION_S_BASES`.
        language: Language code for syllable counting (``"en"``, ``"de"``,
            ``"fr"``). Defaults to :attr:`DEFAULT_LANGUAGE`.
    """

    #: Apostrophe suffixes that unambiguously indicate a contraction.
    #: ``"t"`` covers ``n't`` (don't, can't, …); the others are ``'re``,
    #: ``'ve``, ``'ll``, ``'d``, ``'m``. Class-level annotated default +
    #: constructor injection — RULE-18 pattern.
    DEFAULT_CONTRACTION_SUFFIXES: tuple[str, ...] = (
        "t",
        "re",
        "ve",
        "ll",
        "d",
        "m",
    )

    #: Bases that form valid ``'s`` contractions (pronoun + common words).
    #: A noun + ``'s`` (possessive) is NOT a contraction. Class-level
    #: annotated default + constructor injection — RULE-18 pattern.
    DEFAULT_CONTRACTION_S_BASES: frozenset[str] = frozenset(
        {
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "that",
            "who",
            "what",
            "where",
            "when",
            "why",
            "how",
            "there",
            "here",
            "let",
        }
    )

    #: Default language for syllable counting.
    DEFAULT_LANGUAGE: LanguageCode = "en"

    def __init__(
        self,
        *,
        contraction_suffixes: tuple[str, ...] = DEFAULT_CONTRACTION_SUFFIXES,
        contraction_s_bases: frozenset[str] = DEFAULT_CONTRACTION_S_BASES,
        language: LanguageCode = DEFAULT_LANGUAGE,
    ) -> None:
        self._contraction_suffixes = contraction_suffixes
        self._contraction_s_bases = contraction_s_bases
        self._language = language

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        utterances: list[AttributedUtterance],
        *,
        verbal_tics: dict[str, list[str]] | None = None,
    ) -> dict[str, VoiceMetrics]:
        """Compute per-character voice metrics from attributed utterances.

        Utterances are grouped by ``speaker``; utterances with
        ``speaker=None`` are skipped (ADR-055 Decision 3 — left for the LLM
        agent to resolve inline).

        Args:
            utterances: Attributed dialogue utterances (from
                :class:`DialogueParser`).
            verbal_tics: Optional mapping from speaker name to candidate
                tic phrases. When provided, ``verbal_tic_frequency`` is a
                dict of ``{phrase: rate}``; when absent or the speaker is
                missing from the mapping, it is ``None``.

        Returns:
            Mapping from speaker name to :class:`VoiceMetrics`. Empty when
            no attributed utterances are supplied.
        """
        # Group utterance texts by speaker (skip unattributed).
        groups: dict[str, list[str]] = {}
        for utt in utterances:
            if utt.speaker is None:
                continue
            groups.setdefault(utt.speaker, []).append(utt.text)

        results: dict[str, VoiceMetrics] = {}
        for speaker, texts in groups.items():
            candidates = verbal_tics.get(speaker) if verbal_tics else None
            results[speaker] = self._compute_metrics(texts, candidates)
        return results

    # ------------------------------------------------------------------
    # Core computation
    # ------------------------------------------------------------------

    def _compute_metrics(
        self,
        texts: list[str],
        verbal_tic_candidates: list[str] | None,
    ) -> VoiceMetrics:
        """Compute all metrics for a single character's utterance texts."""
        all_words: list[str] = []
        sentence_lengths: list[int] = []
        for text in texts:
            if not text or not text.strip():
                continue
            all_words.extend(self._extract_words(text))
            sentence_lengths.extend(self._sentence_word_counts(text))

        # RULE-11: no words → all-None VoiceMetrics (graceful degradation).
        if not all_words:
            return VoiceMetrics()

        total_words = len(all_words)

        avg_sent_len, sent_len_std = self._sentence_length_stats(sentence_lengths)

        return VoiceMetrics(
            avg_sentence_length=avg_sent_len,
            sentence_length_std=sent_len_std,
            type_token_ratio=self._type_token_ratio(all_words),
            avg_syllables_per_word=self._avg_syllables_per_word(all_words),
            contraction_rate=self._contraction_rate(all_words),
            verbal_tic_frequency=self._verbal_tic_frequency(
                texts, total_words, verbal_tic_candidates
            ),
            punctuation_profile=self._punctuation_profile(texts, total_words),
        )

    # ------------------------------------------------------------------
    # Tokenisation helpers (mirror FormulaReadabilityAnalyzer's approach)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_words(text: str) -> list[str]:
        """Extract lowercase word tokens, keeping apostrophes for contraction detection."""
        return [w.lower() for w in _WORD_RE.findall(text)]

    @staticmethod
    def _sentence_word_counts(text: str) -> list[int]:
        """Split *text* into sentences and return the word count of each."""
        counts: list[int] = []
        for sent in _SENTENCE_SPLIT_RE.split(text.strip()):
            if not sent.strip():
                continue
            words = VoiceMetricsAnalyzer._extract_words(sent)
            if words:
                counts.append(len(words))
        return counts

    # ------------------------------------------------------------------
    # Metric helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sentence_length_stats(lengths: list[int]) -> tuple[float, float]:
        """Return ``(mean, population std)`` of per-sentence word counts.

        Population standard deviation (``ddof=0``) is used so that a single
        sentence yields ``std=0.0`` (ADR-021 stability).
        """
        if not lengths:
            return 0.0, 0.0
        avg = float(mean(lengths))
        std = pstdev(lengths) if len(lengths) > 1 else 0.0
        return avg, float(std)

    @staticmethod
    def _type_token_ratio(words: list[str]) -> float:
        """Unique lowercase tokens / total tokens, bounded ``[0.0, 1.0]``."""
        if not words:
            return 0.0
        return len(set(words)) / len(words)

    def _avg_syllables_per_word(self, words: list[str]) -> float:
        """Average syllables per word via :func:`count_syllables` (core/nlp)."""
        if not words:
            return 0.0
        total = sum(count_syllables(w, self._language) for w in words)
        return total / len(words)

    def _contraction_rate(self, words: list[str]) -> float:
        """Fraction of tokens that are English contractions."""
        if not words:
            return 0.0
        count = sum(1 for w in words if self._is_contraction(w))
        return count / len(words)

    def _is_contraction(self, word: str) -> bool:
        """True if *word* (lowercase, with apostrophe) is a contraction.

        A token with an apostrophe is a contraction when the suffix is an
        unambiguous contraction marker (``n't``, ``'re``, ``'ve``, ``'ll``,
        ``'d``, ``'m``) or when the suffix is ``'s`` and the base is a
        pronoun / common contraction-forming word. A noun + ``'s``
        (possessive) is NOT a contraction.
        """
        if "'" not in word:
            return False
        base, _, suffix = word.partition("'")
        suffix = suffix.lower()
        return suffix in self._contraction_suffixes or (
            suffix == "s" and base.lower() in self._contraction_s_bases
        )

    @staticmethod
    def _verbal_tic_frequency(
        texts: list[str],
        total_words: int,
        candidates: list[str] | None,
    ) -> dict[str, float] | None:
        """Count candidate phrase occurrences / total words (case-insensitive).

        Returns ``None`` when no candidates are supplied (the caller did not
        pass ``verbal_tics`` for this speaker). Returns ``{phrase: 0.0}``
        when candidates are supplied but none occur in the text.
        """
        if candidates is None:
            return None
        if total_words == 0:
            return dict.fromkeys(candidates, 0.0)
        combined = " ".join(texts)
        result: dict[str, float] = {}
        for tic in candidates:
            pattern = r"\b" + re.escape(tic) + r"\b"
            count = len(re.findall(pattern, combined, re.IGNORECASE))
            result[tic] = count / total_words
        return result

    @staticmethod
    def _punctuation_profile(
        texts: list[str],
        total_words: int,
    ) -> dict[str, float]:
        """Count punctuation habits / total words.

        Habits tracked: ``exclamation`` (``!``), ``question`` (``?``),
        ``ellipsis`` (``...`` or ``\\u2026``), ``em_dash`` (``\\u2014``).
        Single periods and commas are not tracked — they are too ubiquitous
        to be distinctive voice markers.
        """
        if total_words == 0:
            return dict.fromkeys(_PUNCTUATION_HABITS, 0.0)
        combined = " ".join(texts)
        return {
            "exclamation": combined.count("!") / total_words,
            "question": combined.count("?") / total_words,
            "ellipsis": len(_ELLIPSIS_RE.findall(combined)) / total_words,
            "em_dash": combined.count(_EM_DASH) / total_words,
        }
