"""Lexicons for AuthorMetricsAnalyzer (ANAL-007 / ADR-074).

Pure-data module holding the curated lexicon + suffix + pattern sets used by
:class:`~narrare_core.analysis.author_metrics.AuthorMetricsAnalyzer`. Extracted
from ``author_metrics.py`` so the analyzer module stays under the RULE-04
file-size limit and the lexicons can be reviewed/tuned independently (they
are eval-tunable via ADR-032 / ADR-074).

All sets are module-level constants (≤5 top-level names — RULE-18 safe).
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# description_density — adjective / adverb suffix proxy
# ---------------------------------------------------------------------------
#:
#: A crude but deterministic modifier-density proxy. Suffix-based heuristics
#: catch a useful fraction of English adjectives / adverbs without spaCy POS
#: (RULE-08 / ADR-021 determinism + provisional per ADR-074 + spec table).
#: False positives (e.g. "decision" ending in -sion, "lion" not adj) and false
#: negatives are accepted — the metric is eval-tunable (ADR-032).

ADJECTIVE_SUFFIXES: tuple[str, ...] = (
    "ous",
    "ful",
    "less",
    "ive",
    "able",
    "ible",
    "al",
    "ic",
    "ish",
    "y",
    "en",
    "ed",  # past-participle adjectives ("broken door")
    "ing",  # present-participle adjectives ("rushing water")
)
ADVERB_SUFFIXES: tuple[str, ...] = (
    "ly",
    "wise",
    "ward",
    "wards",
)


# ---------------------------------------------------------------------------
# action_introspection_ratio — introspection-marker vs action-verb density
# ---------------------------------------------------------------------------
#:
#: 0.0 = action-heavy, 1.0 = introspection-heavy. The proxy counts
#: introspection markers (thought verbs + reflection cues) vs action verbs
#: (motion + physical-action verbs). Both sets are small + curated; the metric
#: is provisional (spec table). The ratio is introspection_count /
#: (introspection_count + action_count), bounded [0, 1] by construction.
#: Returns 0.0 when neither set occurs (no signal → default to action-neutral).

INTROSPECTION_CUES: tuple[str, ...] = (
    # Thought verbs.
    "thought",
    "think",
    "thinking",
    "wondered",
    "wonder",
    "wondering",
    "considered",
    "consider",
    "considering",
    "pondered",
    "ponder",
    "mused",
    "reflected",
    "reflect",
    "reflecting",
    "remembered",
    "remember",
    "remembering",
    "recalled",
    "recall",
    "recalling",
    "realized",
    "realize",
    "realizing",
    "knew",
    "know",
    "knowing",
    "felt",
    "feel",
    "feeling",
    "imagined",
    "imagine",
    "imagining",
    "supposed",
    "suppose",
    "supposing",
    "guessed",
    "guess",
    "guessing",
    # Explicit reflection cues.
    "perhaps",
    "maybe",
    "inside",
)

ACTION_CUES: tuple[str, ...] = (
    # Motion verbs (high-frequency).
    "ran",
    "run",
    "running",
    "walked",
    "walk",
    "walking",
    "jumped",
    "jump",
    "jumping",
    "leapt",
    "leap",
    "leaping",
    "climbed",
    "climb",
    "climbing",
    "crawled",
    "crawl",
    "crawling",
    "charged",
    "charge",
    "charging",
    "rushed",
    "rush",
    "rushing",
    "sprinted",
    "sprint",
    "sprinting",
    # Physical-action verbs.
    "grabbed",
    "grab",
    "grabbing",
    "struck",
    "strike",
    "striking",
    "hit",
    "hitting",
    "punched",
    "punch",
    "punching",
    "kicked",
    "kick",
    "kicking",
    "threw",
    "throw",
    "throwing",
    "caught",
    "catch",
    "catching",
    "pivoted",
    "pivot",
    "pivoting",
    "dodged",
    "dodge",
    "dodging",
)


# ---------------------------------------------------------------------------
# metaphor_density — simile / figurative-cue proxy (CRUDEST, provisional)
# ---------------------------------------------------------------------------
#:
#: Per the spec's metaphor_density decision (Q1 resolution), this is a
#: deterministic simile/figurative-cue proxy — option B, NOT LLM-assist
#: (which would violate the descriptive/metric boundary + ADR-021 determinism).
#: It catches similes, not full metaphors. Crude but stable + cheap — exactly
#: what a drift-comparable metric must be.

#: Simile cue patterns ("like a", "as a", "as if", "as though"). The leading
#: ``\b`` + trailing non-capturing group prevents matching across word
#: boundaries incorrectly (e.g. "alike" alone is not a simile cue).
SIMILE_CUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\blike\s+(?:a|an|the)\b", re.IGNORECASE),
    re.compile(r"\bas\s+(?:a|an|the)\b", re.IGNORECASE),
    re.compile(r"\bas\s+if\b", re.IGNORECASE),
    re.compile(r"\bas\s+though\b", re.IGNORECASE),
)

#: Small curated figurative-cue lexicon — words that strongly mark figurative
#: language. Eval-tunable (ADR-032).
FIGURATIVE_LEXICON: tuple[str, ...] = (
    "metaphor",
    "metaphorical",
    "figurative",
    "symbolic",
)
